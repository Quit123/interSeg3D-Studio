"""
This module provides functions to render object views from a point cloud or mesh with materials
using Open3D. It offers multiple modes to indicate the object, such as an "outline" (via a convex hull)
or a "full" mode that recolors masked points. Additionally, it includes a test function to generate
camera positions, save a combined scene (with camera markers), and render images from these views.
"""

import os
from pathlib import Path
from typing import List, Tuple, Union, Optional

import numpy as np
import open3d as o3d
from open3d.visualization import rendering

from scipy.spatial import KDTree
from sklearn.decomposition import PCA
from scipy.stats import multivariate_normal

def load_geometry_from_file(
        file_path: str | Path,
        background_color: List[float],
        debug: bool = False
) -> Tuple[str, np.ndarray, np.ndarray, Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]]:
    """
    Loads a geometry from the specified file, determining whether it is a mesh or a point cloud.

    Parameters:
        file_path (str or Path): Path to the file containing the geometry.
        background_color (List[float]): Color to use for vertices without specified colors.
        debug (bool): If True, prints debug information.

    Returns:
        Tuple containing:
            - geometry_type (str): "mesh" or "pointcloud" depending on the file content.
            - coords (np.ndarray): Array of vertex or point coordinates.
            - colors (np.ndarray): Array of vertex or point colors.
            - geometry (o3d.geometry.TriangleMesh or o3d.geometry.PointCloud): The loaded geometry object.

    Raises:
        None explicitly; errors from Open3D are propagated.
    """
    # Determine if the file contains a mesh (triangles) or a point cloud.
    file_path = str(file_path)

    file_type = o3d.io.read_file_geometry_type(file_path)
    if file_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
        geometry = o3d.io.read_triangle_mesh(file_path)
        coords = np.array(geometry.vertices)
        # Use vertex colors if available, otherwise fill with the background color.
        colors = (np.array(geometry.vertex_colors)
                  if geometry.has_vertex_colors()
                  else np.tile(background_color, (len(coords), 1)))
        geometry_type = "mesh"
        if debug:
            print("Loaded mesh geometry from file.")
    else:
        geometry = o3d.io.read_point_cloud(file_path)
        coords = np.array(geometry.points)
        # Use point colors if available, otherwise fill with the background color.
        colors = (np.array(geometry.colors)
                  if geometry.has_colors()
                  else np.tile(background_color, (len(coords), 1)))
        geometry_type = "pointcloud"
        if debug:
            print("Loaded point cloud geometry from file.")
    return geometry_type, coords, colors, geometry


def process_mask_mode(
        mask: np.ndarray,
        coords: np.ndarray,
        colors: np.ndarray,
        mask_mode: str,
        highlight_color: List[float]
) -> Tuple[np.ndarray, Optional[o3d.geometry.LineSet]]:
    """
    Processes the mask on the geometry based on the specified mask mode.

    Parameters:
        mask (np.ndarray): Boolean array indicating masked points.
        coords (np.ndarray): Array of vertex/point coordinates.
        colors (np.ndarray): Array of vertex/point colors.
        mask_mode (str): Mode for processing the mask ("full" or "outline").
        highlight_color (List[float]): Color to apply to masked points or outline.

    Returns:
        A tuple containing:
            - updated_colors (np.ndarray): Modified colors array after applying the mask.
            - outline (o3d.geometry.LineSet or None): LineSet representing the convex hull outline (if applicable).

    Raises:
        ValueError: If mask_mode is not "outline" or "full", or if no points are selected by the mask.
    """
    updated_colors = colors.copy()
    outline = None

    if mask_mode == "full":
        # For full mode, update the color of all masked points to the highlight color.
        updated_colors[mask] = highlight_color
    elif mask_mode == "outline":
        if not mask.any():
            raise ValueError("The mask did not select any points.")
        # Compute the convex hull of the masked points to generate an outline.
        object_points = coords[mask]
        object_pcd = o3d.geometry.PointCloud()
        object_pcd.points = o3d.utility.Vector3dVector(object_points)
        hull, _ = object_pcd.compute_convex_hull()
        outline = o3d.geometry.LineSet.create_from_triangle_mesh(hull)
        outline.colors = o3d.utility.Vector3dVector(
            np.tile(highlight_color, (len(outline.lines), 1)))
    else:
        raise ValueError("mask_mode must be 'outline' or 'full'.")
    return updated_colors, outline


def create_vis_geometry(
        geometry_type: str,
        coords: np.ndarray,
        vis_colors: np.ndarray,
        original_geometry: Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]
) -> Union[o3d.geometry.TriangleMesh, o3d.geometry.PointCloud]:
    """
    Creates a visualization geometry based on the type of the original geometry.

    Parameters:
        geometry_type (str): Type of geometry ("mesh" or "pointcloud").
        coords (np.ndarray): Array of vertex or point coordinates.
        vis_colors (np.ndarray): Array of colors for visualization.
        original_geometry (o3d.geometry.TriangleMesh or o3d.geometry.PointCloud): Original geometry to derive topology.

    Returns:
        A new geometry object (TriangleMesh or PointCloud) configured for visualization.
    """
    if geometry_type == "mesh":
        vis_geometry = o3d.geometry.TriangleMesh()
        vis_geometry.vertices = o3d.utility.Vector3dVector(coords)
        vis_geometry.vertex_colors = o3d.utility.Vector3dVector(vis_colors)
        vis_geometry.triangles = original_geometry.triangles
        vis_geometry.compute_vertex_normals()
    else:
        vis_geometry = o3d.geometry.PointCloud()
        vis_geometry.points = o3d.utility.Vector3dVector(coords)
        vis_geometry.colors = o3d.utility.Vector3dVector(vis_colors)
        vis_geometry.estimate_normals()
    return vis_geometry


def render_object_views(
        point_cloud_path: str,
        mask: Union[List[bool], np.ndarray],
        camera_pos: List[List[float]],
        output_dir: str = "./object_views",
        image_size: Tuple[int, int] = (1280, 720),
        highlight_color: List[float] = [1.0, 0.0, 0.0],
        background_color: List[float] = [0.8, 0.8, 0.8],
        view_angle: float = 60.0,
        mask_mode: str = "outline",  # "outline" or "full"
        debug: bool = True,

        look_outward: bool = False,  # 新增参数
        scene_center: List[float] = None,
) -> List[str]:
    """
    Renders views of an object based on a mask and a set of camera positions.

    Parameters:
        point_cloud_path (str): Path to the point cloud or mesh file.
        mask (List[bool] or np.ndarray): Boolean mask indicating object points.
        camera_pos (List[List[float]]): List of camera positions (each as [x, y, z]).
        output_dir (str): Directory to save the rendered images.
        image_size (Tuple[int, int]): Width and height of the rendered images.
        highlight_color (List[float]): Color used for highlighting the masked object.
        background_color (List[float]): Background color for rendering.
        view_angle (float): Camera field of view angle in degrees.
        mask_mode (str): Visualization mode ("outline" or "full").
        debug (bool): If True, prints debug messages.

    Returns:
        List[str]: List of file paths to the rendered image views.

    Raises:
        ValueError: If the mask length does not match the number of points or if no points are selected.
    """
    # Ensure output directory exists.
    os.makedirs(output_dir, exist_ok=True)

    # Load the geometry from the specified file.
    geometry_type, coords, colors, geometry = load_geometry_from_file(point_cloud_path, background_color, debug)
    mask_bool = np.array(mask, dtype=bool)

    if mask_bool.shape[0] != len(coords):
        raise ValueError("Mask length does not match number of points in the geometry.")

    # Process the mask to get visualization colors and optional outline.
    vis_colors, outline = process_mask_mode(mask_bool, coords, colors, mask_mode, highlight_color)
    vis_geometry = create_vis_geometry(geometry_type, coords, vis_colors, geometry)

    width, height = image_size
    renderer = rendering.OffscreenRenderer(width, height)
    # Ensure the background color has an alpha value.
    bg_color = background_color + [1.0] if len(background_color) == 3 else background_color
    renderer.scene.set_background(bg_color)

    # Set up a simple material for unlit rendering.
    material = rendering.MaterialRecord()
    material.shader = "defaultUnlit"
    renderer.scene.add_geometry("geometry", vis_geometry, material)
    if mask_mode == "outline" and outline is not None:
        renderer.scene.add_geometry("outline", outline, material)

    near_plane = 0.1
    far_plane = 1000.0

    if not mask_bool.any():
        raise ValueError("The mask did not select any points.")
    # Compute the center of the masked object.
    object_center = np.mean(coords[mask_bool], axis=0)

    image_paths = []
    # Iterate over each camera position, render the scene, and save the output image.
    for idx, eye in enumerate(camera_pos):
        eye = np.array(eye)
        if look_outward:
            target = 2 * eye - scene_center

            up = np.array([0, 0, 1])

            renderer.scene.camera.look_at(target, eye, up)
        else:
            renderer.scene.camera.look_at(object_center, eye, np.array([0, 0, 1]))
        # renderer.scene.camera.look_at(object_center, eye, np.array([0, 0, 1]))
        aspect = width / height
        renderer.scene.camera.set_projection(
            view_angle, aspect, near_plane, far_plane, rendering.Camera.FovType.Vertical
        )
        img = renderer.render_to_image()
        image_path = os.path.join(output_dir, f"view_{idx:03d}.png")
        o3d.io.write_image(image_path, img)
        image_paths.append(image_path)
        if debug:
            print(f"Saved view {idx} to {image_path}")
    return image_paths


def compute_object_center_and_radius(
        mask: np.ndarray, coords: np.ndarray
) -> Tuple[np.ndarray, float]:
    """
    Computes the center and the maximum distance (bounding radius) of the object defined by the mask.

    Parameters:
        mask (np.ndarray): Boolean mask selecting object points.
        coords (np.ndarray): Array of vertex/point coordinates.

    Returns:
        Tuple containing:
            - center (np.ndarray): The mean position of the masked points.
            - bounding_radius (float): The maximum distance from the center to any masked point.

    Raises:
        ValueError: If no points are selected by the mask.
    """
    if not mask.any():
        raise ValueError("No masked points found in the geometry.")
    masked_coords = coords[mask]
    center = np.mean(masked_coords, axis=0)
    bounding_radius = np.max(np.linalg.norm(masked_coords - center, axis=1))
    return center, bounding_radius


def create_camera_markers(
        camera_positions: List[List[float]], bounding_radius: float
) -> o3d.geometry.PointCloud:
    """
    Creates visual markers at the specified camera positions.

    Parameters:
        camera_positions (List[List[float]]): List of camera positions.
        bounding_radius (float): Bounding radius of the object (used to size the markers).

    Returns:
        o3d.geometry.PointCloud: A point cloud containing markers for the camera positions.
    """
    camera_marker_clouds = []
    # Determine a sphere radius for the camera markers.
    sphere_radius = bounding_radius * 0.1 if bounding_radius > 0 else 0.1
    for pos in camera_positions:
        # Create a sphere mesh for each camera marker.
        sphere_mesh = o3d.geometry.TriangleMesh.create_sphere(radius=sphere_radius)
        sphere_mesh.translate(np.array(pos))
        sphere_mesh.paint_uniform_color([0.0, 1.0, 0.0])
        # Sample points uniformly from the sphere mesh.
        marker = sphere_mesh.sample_points_uniformly(number_of_points=500)
        camera_marker_clouds.append(marker)
    # Combine all markers into one point cloud.
    all_points = [np.asarray(cloud.points) for cloud in camera_marker_clouds]
    all_colors = [np.asarray(cloud.colors) for cloud in camera_marker_clouds]
    if all_points:
        all_points = np.vstack(all_points)
        all_colors = np.vstack(all_colors)
        camera_cloud = o3d.geometry.PointCloud()
        camera_cloud.points = o3d.utility.Vector3dVector(all_points)
        camera_cloud.colors = o3d.utility.Vector3dVector(all_colors)
    else:
        camera_cloud = o3d.geometry.PointCloud()
    return camera_cloud


def sample_line_points(line_set, num_samples=20):
    """
    Samples additional points along each line segment in the provided LineSet.

    Parameters:
        line_set (o3d.geometry.LineSet): The LineSet to sample points from.
        num_samples (int): Number of points to sample per line segment.

    Returns:
        np.ndarray: Array of sampled points.
    """
    points = np.asarray(line_set.points)
    sampled_points = []
    # Each line is defined by two point indices.
    for line in np.asarray(line_set.lines):
        start = points[line[0]]
        end = points[line[1]]
        # Sample num_samples points along the line (including endpoints)
        for t in np.linspace(0, 1, num_samples):
            sample = start * (1 - t) + end * t
            sampled_points.append(sample)
    return np.array(sampled_points)


def test_camera_positions(
        point_cloud_path: str | Path,
        mask: Union[np.ndarray, str],
        output_dir: str = "./camera_test",
        view_angle: float = 60.0,
        distance_factor: float = 2.0,
        num_positions: int = 8,
        camera_height: Optional[float] = None,
        mask_mode: str = "outline",
        highlight_color: List[float] = [1.0, 0.0, 0.0],
        obj_id: int = 1,

        look_outward: bool = False,
        overlap_ratio: float = 0.2,
) -> List[str]:
    """
    Tests camera positions by generating multiple views of the scene, adding camera markers,
    and saving a combined scene (as a PLY file) with the masked object processed according to mask_mode.

    Parameters:
        point_cloud_path (str or Path): Path to the point cloud or mesh file.
        mask (np.ndarray or str): Boolean mask or file path to a saved mask (.npy).
        output_dir (str): Directory to save outputs including rendered views.
        view_angle (float): Camera field of view in degrees.
        distance_factor (float): Factor to determine camera distance from the object.
        num_positions (int): Number of camera positions to generate.
        camera_height (Optional[float]): Height of the camera; if None, computed automatically.
        mask_mode (str): Visualization mode ("outline" or "full") used for masking.
        highlight_color (List[float]): Color used for highlighting the masked object.
        obj_id (int): Object ID.

    Returns:
        List[str]: List of file paths to the rendered image views.

    Raises:
        ValueError: If the mask file format is unsupported or if the mask length does not match.
    """
    # If mask is provided as a file path, load it.
    if isinstance(mask, str):
        if mask.endswith('.npy'):
            mask = np.load(mask)
        else:
            raise ValueError(f"Unsupported mask file format: {mask}")

    # Load the geometry using a fixed background color.
    geometry_type, coords, colors, geometry = load_geometry_from_file(point_cloud_path, [0.5, 0.5, 0.5])

    # Create a copy of the mask as a numpy array
    mask_array = np.array(mask, dtype=int)

    # Create a boolean mask for the specified object ID
    obj_mask: np.ndarray[bool] = mask_array == obj_id
    if obj_mask.shape[0] != len(coords):
        raise ValueError("Mask length does not match number of points in the geometry.")

    # Process the obj_mask to update colors (or generate an outline) per mask_mode.
    vis_colors, outline = process_mask_mode(obj_mask, coords, colors.copy(), mask_mode, highlight_color)
    # Create the visualization geometry using the updated colors.
    vis_geometry = create_vis_geometry(geometry_type, coords, vis_colors, geometry)

    # center, bounding_radius = compute_object_center_and_radius(obj_mask, coords)
    # ******************************************************************************
    if look_outward:
        # The central of whole point cloud and surrounding radius
        center = compute_cloud_center(coords)
        # center, target = compute_camera_position(coords)
        bounding_radius = 0.5

        view_angle = 90.0
        distance_factor = 0.1
        aspect_ratio = 1280 / 720 # render_object_views image_size
        vertical_fov_rad = np.radians(view_angle)
        horizontal_fov_rad = 2 * np.arctan(np.tan(vertical_fov_rad / 2) * aspect_ratio)
        horizontal_fov = np.degrees(horizontal_fov_rad)

        effective_fov = horizontal_fov * (1 - overlap_ratio)
        num_positions = int(np.ceil(360 / effective_fov))
        print(f"horizontal_fov: {horizontal_fov:.2f}°")
        print(f"effective_fov: {effective_fov:.2f}°")
        print("num_positions", num_positions)
        print(f"bounding_radius: {bounding_radius}")
    else:
        center, bounding_radius = compute_object_center_and_radius(obj_mask, coords)
    # ******************************************************************************

    # Compute camera height if not provided.
    if camera_height is None:
        camera_height = np.min(coords[:, 2]) + 1.5

    # Generate camera positions evenly around the object.
    camera_positions = []
    radius = bounding_radius * distance_factor
    for i in range(num_positions):
        angle = 2 * np.pi * i / num_positions
        x = center[0] + radius * np.cos(angle)
        y = center[1] + radius * np.sin(angle)
        camera_positions.append([x, y, camera_height])

    # outlook
    scene_center = [center[0], center[1], camera_height]

    # Create camera markers.
    camera_cloud = create_camera_markers(camera_positions, bounding_radius)

    # Build the scene point cloud from the visualization geometry.
    if geometry_type == "mesh":
        scene_cloud = o3d.geometry.PointCloud()
        scene_cloud.points = o3d.utility.Vector3dVector(np.asarray(vis_geometry.vertices))
        scene_cloud.colors = o3d.utility.Vector3dVector(np.asarray(vis_geometry.vertex_colors))
    else:
        scene_cloud = vis_geometry

    # If in "outline" mode, sample additional points from the outline and merge into the scene.
    if mask_mode == "outline" and outline is not None:
        sampled_outline_points = sample_line_points(outline, num_samples=20)
        outline_colors = np.tile(np.array(highlight_color), (len(sampled_outline_points), 1))
        outline_cloud = o3d.geometry.PointCloud()
        outline_cloud.points = o3d.utility.Vector3dVector(sampled_outline_points)
        outline_cloud.colors = o3d.utility.Vector3dVector(outline_colors)
        # Merge the outline cloud with the scene cloud.
        combined_points = np.vstack((np.asarray(scene_cloud.points), np.asarray(outline_cloud.points)))
        combined_colors = np.vstack((np.asarray(scene_cloud.colors), np.asarray(outline_cloud.colors)))
        scene_cloud.points = o3d.utility.Vector3dVector(combined_points)
        scene_cloud.colors = o3d.utility.Vector3dVector(combined_colors)

    # Combine the scene (with the masked object) with camera marker points.
    combined_points = np.vstack((np.asarray(scene_cloud.points), np.asarray(camera_cloud.points)))
    combined_colors = np.vstack((np.asarray(scene_cloud.colors), np.asarray(camera_cloud.colors)))
    combined_scene = o3d.geometry.PointCloud()
    combined_scene.points = o3d.utility.Vector3dVector(combined_points)
    combined_scene.colors = o3d.utility.Vector3dVector(combined_colors)

    # Save the combined scene (with camera markers and masked object) as a PLY file.
    os.makedirs(output_dir, exist_ok=True)
    ply_output_path = os.path.join(output_dir, "scene_with_camera_markers.ply")
    o3d.io.write_point_cloud(ply_output_path, combined_scene)
    print(f"Scene PLY with camera markers saved to {ply_output_path}")

    # Render object views using the provided mask_mode.
    return render_object_views(
        point_cloud_path=point_cloud_path,
        mask=obj_mask,
        camera_pos=camera_positions,
        output_dir=output_dir,
        view_angle=view_angle,
        mask_mode=mask_mode,
        debug=True,
        look_outward=look_outward,
        scene_center=scene_center,
    )

# *********************************************************************

# def compute_cloud_center(coords: np.ndarray, k_neighbors: int = 50, std_ratio: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
#     """预处理点云并计算PCA主方向"""
#     if len(coords) == 0:
#         return np.array(0.0), np.array(0.0), np.array(0.0)
#
#     # 去除离群点（同之前方法）
#     tree = KDTree(coords)
#     distances, _ = tree.query(coords, k=k_neighbors + 1)
#     avg_distances = np.mean(distances[:, 1:], axis=1)
#     mean_dist = np.mean(avg_distances)
#     std_dist = np.std(avg_distances)
#     threshold = mean_dist + std_ratio * std_dist
#     filtered_coords = coords[avg_distances < threshold]
#     if len(filtered_coords) == 0:
#         filtered_coords = coords
#
#     # 计算PCA主方向
#     pca = PCA(n_components=3)
#     pca.fit(filtered_coords)
#     return pca.mean_, pca.components_, filtered_coords
#
#
# def voxelize_along_pca(coords: np.ndarray, pca_mean: np.ndarray, pca_axes: np.ndarray,
#                        voxel_size: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
#     """沿PCA主方向体素化点云，返回每个体素的中心坐标和点数"""
#     # 将点云转换到PCA坐标系
#     centered_coords = coords - pca_mean
#     projected_coords = np.dot(centered_coords, pca_axes.T)
#
#     # 计算体素网格范围
#     min_bounds = np.min(projected_coords, axis=0)
#     max_bounds = np.max(projected_coords, axis=0)
#     num_voxels = np.ceil((max_bounds - min_bounds) / voxel_size).astype(int)
#
#     # 体素化并统计点数
#     voxel_grid = {}
#     for point in projected_coords:
#         voxel_idx = tuple(((point - min_bounds) // voxel_size).astype(int))
#         if voxel_idx not in voxel_grid:
#             voxel_grid[voxel_idx] = []
#         voxel_grid[voxel_idx].append(point)
#
#     # 生成体素中心坐标（PCA坐标系）
#     voxel_centers_pca = []
#     voxel_counts = []
#     for idx in voxel_grid:
#         center_pca = min_bounds + (np.array(idx) + 0.5) * voxel_size
#         voxel_centers_pca.append(center_pca)
#         voxel_counts.append(len(voxel_grid[idx]))
#
#     # 转换回原始坐标系
#     voxel_centers = np.dot(np.array(voxel_centers_pca), pca_axes) + pca_mean
#     return voxel_centers, np.array(voxel_counts)
#
#
# def find_low_density_position(coords: np.ndarray, voxel_size: float = 1.0,
#                               density_percentile: float = 10.0) -> np.ndarray:
#     """寻找低密度体素区域的中心位置"""
#     pca_mean, pca_axes, filtered_coords = compute_cloud_center(coords)
#     voxel_centers, voxel_counts = voxelize_along_pca(filtered_coords, pca_mean, pca_axes, voxel_size)
#
#     # 筛选密度最低的体素（排除空体素）
#     valid_indices = np.where(voxel_counts > 0)[0]
#     if len(valid_indices) == 0:
#         return pca_mean  # 无有效体素时回退到中心
#
#     valid_counts = voxel_counts[valid_indices]
#     threshold = np.percentile(valid_counts, density_percentile)
#     low_density_indices = valid_indices[valid_counts <= threshold]
#
#     # 选择距离场景中心最近的候选位置
#     low_density_centers = voxel_centers[low_density_indices]
#     distances_to_center = np.linalg.norm(low_density_centers - pca_mean, axis=1)
#     best_candidate = low_density_centers[np.argmax(distances_to_center)]  # 选择最远的低密度点（通常在外部）
#
#     return best_candidate
#
#
# def compute_camera_position(coords: np.ndarray, fov_deg: float = 60.0,
#                             padding_scale: float = 1.5, voxel_size: float = 1.0) -> tuple:
#     """计算摄像头的位置和朝向"""
#     # 确定低密度候选位置
#     candidate_pos = find_low_density_position(coords, voxel_size)
#     pca_mean, pca_axes, _ = compute_cloud_center(coords)
#
#     # 计算包围盒尺寸
#     centered_coords = coords - pca_mean
#     projected_coords = np.dot(centered_coords, pca_axes.T)
#     obb_size = np.max(projected_coords, axis=0) - np.min(projected_coords, axis=0)
#
#     # 计算安全距离（沿主方向反向）
#     main_axis = pca_axes[0]
#     fov_rad = np.radians(fov_deg)
#     max_half_size = np.max(obb_size) / 2.0
#     base_distance = (max_half_size / np.tan(fov_rad / 2)) * padding_scale
#
#     # 调整摄像头位置到安全距离
#     camera_dir = -main_axis  # 沿主方向反向
#     camera_pos = candidate_pos + camera_dir * base_distance
#
#     # 确保摄像头在点云外部：检查到最近点的距离
#     tree = KDTree(coords)
#     min_dist, _ = tree.query(camera_pos.reshape(1, -1), k=1)
#     safe_distance = np.linalg.norm(obb_size) * 0.1  # 最小安全距离为包围盒尺寸的10%
#     if min_dist < safe_distance:
#         camera_pos += camera_dir * (safe_distance - min_dist)
#
#     # 摄像头朝向场景中心
#     return camera_pos, pca_mean

# *********************************************************************

def compute_cloud_center(coords: np.ndarray) -> np.ndarray:
    """计算点云的几何中心（质心）"""
    return np.mean(coords, axis=0)


if __name__ == "__main__":
    from inference import infer

    # Define the path to the point cloud or mesh file.
    point_cloud_path = "agile3d/data/interactive_dataset/scan.ply"

    # Option 1: Generate a mask via inference.
    result_path, mask = infer(
        point_cloud_path=point_cloud_path,
        click_positions=[[1.3158004, 1.5544679, 0.4713757]],
        click_obj_indices=[1],
        output_dir="./outputs"
    )

    # Option 2: Load a mask from file (uncomment if using a file).
    # mask = "path/to/saved/mask.npy"

    # Generate camera views based on the mask and test the camera positions.
    view_paths = test_camera_positions(
        point_cloud_path=point_cloud_path,
        mask=mask,
        output_dir="./object_views/camera_test",
        view_angle=90.0,
        distance_factor=1,
        num_positions=8,
        camera_height=1.5,
        mask_mode="outline",  # or "full" based on your desired visualization

        look_outward=True,
        overlap_ratio=0
    )
    # for outer view
    # view_angle = 90.0,
    # distance_factor = 0.01,
    print(f"Generated {len(view_paths)} views at: {view_paths}")
