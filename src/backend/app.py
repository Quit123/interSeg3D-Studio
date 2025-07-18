import os
import shutil
import tempfile
from typing import Dict, List, Any

import numpy as np
import open3d as o3d
import torch
import subprocess
import uuid
from fastapi import FastAPI, File, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import the pre segmentation module
from pointcloud_filter import filt_pointcloud
from voxelizer import find_position
from view_rendering import test_camera_positions
from segmentor import pre_segment

# Import the inference module
from inference import Click, ClickHandler, PointCloudInference
from visual_obj_recognition import mask_obj_recognition


# Create static directory if it doesn't exist
static_dir = os.path.join(os.getcwd(), "static")
os.makedirs(static_dir, exist_ok=True)

app = FastAPI(title="AGILE3D Interactive Segmentation API")

# Mount the static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Add CORS middleware with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    # List specific origins instead of using wildcard "*"
    allow_origins=["https://localhost:3001", "https://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state (in a real application, you might want to use a database)
current_point_cloud = None
current_point_cloud_path = None
current_inference = None
current_results = None


class InferenceRequest(BaseModel):
    clickData: Dict[str, Dict[str, Any]]  # clickIdx, clickTimeIdx, clickPositions
    cubeSize: float
    objectNames: List[str]


class MaskObjDetectionRequest(BaseModel):
    # "mask" is a list of integers where 0 is background, 1 is first object, 2 is second object, etc.
    mask: list

# script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.abspath(os.path.join(script_dir, '../'))
# pretraining_weights = os.path.join(
#     project_root,
#     'agile3d',
#     'weights',
#     'checkpoint1099.pth'
# )

@app.post("/api/upload")
async def upload_point_cloud(file: UploadFile = File(...)):
    """
    Upload a point cloud file (PLY format)
    """
    global current_point_cloud, current_point_cloud_path, current_inference

    # Create a temporary directory to store the uploaded file
    temp_dir = tempfile.mkdtemp()
    try:
        # Save the uploaded file
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Store the file path for later use
        current_point_cloud_path = file_path

        # Load the point cloud
        pcd_type = o3d.io.read_file_geometry_type(file_path)

        if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
            # It's a mesh
            mesh = o3d.io.read_triangle_mesh(file_path)
            coords = np.array(mesh.vertices)
            colors = np.array(mesh.vertex_colors) if mesh.has_vertex_colors() else np.ones(
                (len(mesh.vertices), 3)) * 0.5
            is_point_cloud = False
        elif pcd_type == o3d.io.FileGeometry.CONTAINS_POINTS:
            # It's a point cloud
            pcd = o3d.io.read_point_cloud(file_path)
            coords = np.array(pcd.points)
            colors = np.array(pcd.colors) if pcd.has_colors() else np.ones((len(pcd.points), 3)) * 0.5
            is_point_cloud = True
        else:
            return JSONResponse(
                status_code=400,
                content={"message": f"Unsupported file format: {file.filename}"}
            )

        # Initialize the inference object
        current_inference = PointCloudInference(
            pretraining_weights='./agile3d/weights/checkpoint1099.pth',
            voxel_size=0.05
        )
        current_inference.load_point_cloud(file_path)

        # Store the full point cloud data (but don't return it to client)
        current_point_cloud = {
            "is_point_cloud": is_point_cloud,
            "coords": coords,
            "colors": colors,
            "point_count": len(coords)
        }

        # Return only metadata - no point cloud data
        return JSONResponse(content={
            "message": "File uploaded successfully",
            "filename": file.filename,
            "pointCount": len(coords),
            "boundingBox": {
                "min": coords.min(axis=0).tolist(),
                "max": coords.max(axis=0).tolist()
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error processing file: {str(e)}"}
        )

@app.post("/api/pre_segmentation")
async def pre_segmentation():
    """
    Decide camera position and do pre segmentation
    """
    global current_point_cloud
    coords = current_point_cloud["coords"]

    # Filt center point cloud
    # center_coords = filt_pointcloud(current_point_cloud["coords"])

    # Determine the height based on the center coordinates
    max_height = coords.max(axis=0)[2]
    min_height = coords.min(axis=0)[2]
    height = (max_height * 2 + min_height) / 3

    # Find the camera position based on the center coordinates and height
    # position = find_position(center_coords, height)

    # Render images(cover all directions)
    in_paths = test_camera_positions (
        point_cloud_path = current_point_cloud_path,
        mask = np.zeros(len(coords), dtype=int),  # Dummy mask, will be pre-segmented
        output_dir = "./camera_test",
        view_angle = 60.0,
        distance_factor = 2.0,
        camera_height = height,
        mask_mode = "full",
        highlight_color = [1.0, 0.0, 0.0],
        obj_id = 1,

        look_outward = True,
        overlap_ratio = 0.2
    )

    # Pre-segment the rendered images
    out_paths = pre_segment(in_paths)

    return JSONResponse(content={
        "message": "Pre-segment completed successfully",
        "outPaths": out_paths,
    })

@app.post("/api/infer")
async def run_inference(request: InferenceRequest):
    """
    Run inference on the current point cloud with the provided click data
    """
    global current_inference, current_results

    if not current_inference:
        return JSONResponse(
            status_code=400,
            content={"message": "No point cloud loaded. Please upload a point cloud first."}
        )

    try:
        # Convert click data to format expected by inference
        click_handler = ClickHandler()

        # Process click positions and create Click objects
        for obj_idx_str, positions in request.clickData["clickPositions"].items():
            obj_idx = int(obj_idx_str)
            obj_name = "background" if obj_idx == 0 else f"object_{obj_idx}"

            # Get time indices for this object
            time_indices = request.clickData["clickTimeIdx"][obj_idx_str]

            for i, pos in enumerate(positions):
                # Create click and add to handler
                click = Click(
                    position=torch.tensor(pos, dtype=torch.float32),
                    obj_idx=obj_idx,
                    obj_name=obj_name,
                    time_idx=time_indices[i],
                    is_positive=True,
                    cube_size=request.cubeSize
                )
                click_handler.clicks.append(click)

                # Find nearest point in the point cloud
                click.find_nearest_point(current_inference.raw_coords_qv)

                # Update model-compatible formats
                click_handler._update_click_dicts(click)

        # Set clicks in the inference object
        current_inference.click_handler = click_handler

        # Run inference
        mask = current_inference.run_inference()

        # Save the results
        result_path = current_inference.save_results(
            mask,
            output_dir="./outputs",
            prefix=f"web_session_{os.path.basename(os.path.splitext(current_point_cloud_path)[0])}"
        )

        # Store the results for later download
        current_results = {
            "mask": mask,
            "result_path": result_path
        }

        # Prepare segmentation results for frontend
        segmentation = mask.tolist()

        print(f'number of positive in mask: {segmentation.count(True)}')

        return JSONResponse(content={
            "message": "Inference completed successfully",
            "segmentedPointCloud": {
                "segmentation": segmentation
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error running inference: {str(e)}"}
        )


def mask_obj_recognition_worker(args):
    obj_id, point_cloud_path, mask_np = args
    # Use mask_np.copy() if necessary to avoid sharing issues.
    return mask_obj_recognition(point_cloud_path, mask_np.copy(), obj_id)


@app.post("/api/mask_obj_recognition")
async def run_mask_obj_recognition(request: MaskObjDetectionRequest):
    """
    Run mask-based object recognition on the current point cloud using provided mask.

    The request body should contain a field "mask" that is a list of integers where:
      - 0 represents the background
      - 1 represents the first object
      - 2 represents the second object, and so on.

    Returns:
      - A list of JSON objects with keys "selected_views", "description", "label", and "cost",
        one for each unique object ID in the mask (excluding background).
    """
    global current_point_cloud_path
    if not current_point_cloud_path:
        return JSONResponse(
            status_code=400,
            content={"message": "No point cloud loaded. Please upload a point cloud first."}
        )
    try:
        mask = request.mask
        if not isinstance(mask, list):
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid mask format. Please provide a list of integers."}
            )

        # Convert to numpy array.
        mask_np = np.array(mask, dtype=int)

        # Find unique object IDs, excluding background (0).
        unique_obj_ids = np.unique(mask_np)
        unique_obj_ids = unique_obj_ids[unique_obj_ids > 0]

        if len(unique_obj_ids) == 0:
            return JSONResponse(
                status_code=400,
                content={"message": "No objects found in the mask (all values are 0/background)."}
            )

        # Prepare arguments for each object.
        work_args = [
            (obj_id, current_point_cloud_path, mask_np)
            for obj_id in unique_obj_ids
        ]

        result = [mask_obj_recognition_worker(args) for args in work_args]

        return JSONResponse(content={
            "message": "Mask object recognition completed successfully",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error running mask object recognition: {str(e)}"}
        )


@app.get("/api/download-results")
async def download_results():
    """
    Download the segmentation results as a PLY file
    """
    if not current_results or not current_results.get("result_path"):
        return JSONResponse(
            status_code=400,
            content={"message": "No results available. Please run inference first."}
        )

    try:
        return FileResponse(
            path=current_results["result_path"],
            filename=os.path.basename(current_results["result_path"]),
            media_type="application/octet-stream"
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Error downloading results: {str(e)}"}
        )


@app.post("/api/render_and_segment")
def render(prompt: str = Body(...)):
    # TODO: 这里你可以用 LLM 或规则解析 prompt
    camera_pos = "2,3,1"
    look_at = "0,0,0"
    output_file = f"/tmp/render_{uuid.uuid4()}.png"

    # 启动 Blender 渲染
    subprocess.run([
        "/path/to/blender", "--background", "--python", "control_blender.py", "--",
        "--pos", camera_pos, "--look", look_at, "--output", output_file
    ])

    # TODO: 分割逻辑，这里可以调用 SAM、OpenCV、mask2former等
    segmentation_result = fake_segment(output_file)

    return {
        "image": output_file,
        "segmentation": segmentation_result
    }

def fake_segment(image_path):
    return {"bbox": [100, 100, 300, 300], "label": "object"}


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    # print("当前工作目录:", os.getcwd())
    # Ensure output directory exists
    os.makedirs("./outputs", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=9500)