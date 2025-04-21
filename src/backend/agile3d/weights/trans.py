import torch
import open3d as o3d
import numpy as np

# 1. 加载 .pth 文件中的点云数据
# 假设 .pth 文件中存储的是一个 3D 点云的坐标（例如 [N, 3] 的张量）
pth_file = 'checkpoint1099.pth'  # 替换为你的 .pth 文件路径
point_cloud_data = torch.load(pth_file)  # 加载 .pth 文件

# 假设 point_cloud_data 是一个形状为 [N, 3] 的 Tensor，其中 N 是点的数量
# 如果是其他格式，需根据实际情况进行调整

# 2. 转换为 NumPy 数组
points = point_cloud_data.numpy()  # 转为 NumPy 数组

# 3. 使用 Open3D 创建点云对象
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(points)

# 4. 保存为 .ply 文件
ply_file = 'output.ply'
o3d.io.write_point_cloud(ply_file, pcd)

print(f"Point cloud saved as {ply_file}")
