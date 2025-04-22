# import bpy
#
# # 设置渲染输出路径
# bpy.context.scene.render.filepath = "./output/render.png"
# # 渲染当前帧
# bpy.ops.render.render(write_still=True)

# blender --background --python test_col.py


import bpy
import numpy as np
from triton.language import dtype

# 加载 PLY 文件
bpy.ops.wm.ply_import(filepath="/media/zhang-bojun/Linux_D/projects/interSeg3D-Studio-fork/src/backend/object_views/camera_test/scene_with_camera_markers_dif.ply")

# 获取导入的模型
obj = bpy.context.object

# 检查是否有顶点颜色
if obj.data.vertex_colors:
    print("模型包含顶点颜色")
else:
    print("模型不包含顶点颜色")

# 如果需要手动创建顶点颜色
if not obj.data.vertex_colors:
    obj.data.vertex_colors.new()

# 应用顶点颜色到材质
for mat in obj.data.materials:
    mat.use_vertex_color_paint = True

# 获取导入的对象
obj = bpy.context.object

mesh = obj.data

# 检查顶点是否有自定义属性
if mesh.attributes:
    print("顶点自定义属性列表:")
    for attr in mesh.attributes:
        print(f"- 属性名称: {attr.name}, 类型: {attr.data_type}")
else:
    print("无顶点自定义属性")

red_attr = mesh.attributes.get("diffuse_red")
green_attr = mesh.attributes.get("diffuse_green")
blue_attr = mesh.attributes.get("diffuse_blue")

if not (red_attr and green_attr and blue_attr):
    raise ValueError("颜色属性缺失")

# 如果没有顶点颜色，则创建
if not mesh.vertex_colors:
    color_layer = mesh.vertex_colors.new(name="Col")
    print("inactive Col")
else:
    color_layer = mesh.vertex_colors.active
    print("active Col")

# # 获取顶点颜色层
# color_layer = obj.data.vertex_colors.active.data
#
# for i, vertex in enumerate(obj.data.vertices):
#     if i <= 3:
#         print("vertex: ", vertex)
#     else:
#         break

# 将颜色数据存储为数组（顶点索引 → 颜色）
color_data = np.zeros(len(mesh.vertices), dtype=np.float64)
colors = np.column_stack((
    red_attr.data.foreach_get("value", color_data),
    green_attr.data.foreach_get("value", color_data),
    blue_attr.data.foreach_get("value", color_data)
))

# 将颜色应用到顶点颜色层（按循环）
for poly in mesh.polygons:
    for loop_idx in poly.loop_indices:
        loop = mesh.loops[loop_idx]
        vertex_idx = loop.vertex_index
        # 转换为RGBA（0.0-1.0）
        r, g, b = colors[vertex_idx]
        color_layer.data[loop_idx].color = (r, g, b, 1.0)

# 打印前3个顶点的颜色值（验证）
print("\n前3个顶点颜色值（0.0-1.0）:")
for i in range(3):
    r, g, b = colors[i]
    print(f"顶点 {i}: R={r:.4f}, G={g:.4f}, B={b:.4f}")

# 刷新视图
bpy.context.view_layer.update()

# # 遍历顶点并手动赋予颜色
# for i, vertex in enumerate(obj.data.vertices):
#     # 从PLY文件中获取RGB值（假设在文件中存储为red, green, blue）
#     red = vertex.co[0]  # 假设red存储在x坐标
#     green = vertex.co[1]  # 假设green存储在y坐标
#     blue = vertex.co[2]  # 假设blue存储在z坐标
#
#     # 将这些RGB值存储为顶点颜色
#     color_layer[i].color = (red, green, blue)
#
# # 更新显示
# bpy.context.view_layer.update()
