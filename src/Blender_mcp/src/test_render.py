import bpy

# 设置PLY文件路径
input_ply_path = "/media/zhang-bojun/Linux_D/projects/interSeg3D-Studio-fork/src/backend/object_views/camera_test/scene_with_camera_markers.ply"

# 清除默认对象
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 使用新的操作符导入PLY
bpy.ops.wm.ply_import(filepath=input_ply_path)  # 注意这里修改为wm.ply_import

# 设置渲染输出路径
output_image_path = "/media/zhang-bojun/Linux_D/projects/interSeg3D-Studio-fork/src/backend/object_views/camera_test/path.png"
bpy.context.scene.render.filepath = output_image_path

# 设置渲染引擎
bpy.context.scene.render.engine = 'CYCLES'

# 执行渲染
bpy.ops.render.render(write_still=True)

print("渲染完成，文件已保存至", output_image_path)