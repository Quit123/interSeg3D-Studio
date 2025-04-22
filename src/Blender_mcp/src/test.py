def modify_ply_colors(input_ply_path, output_ply_path):
    with open(input_ply_path, 'rb') as infile:
        # 读取文件内容
        content = infile.read()

        # 查找头部部分（直到 'end_header'）
        header_end = content.find(b'end_header')

        if header_end == -1:
            print("没有找到 'end_header' 标记")
            return

        # 截取头部（包括 'end_header'）
        header = content[:header_end + len(b'end_header')]

        # 将头部从二进制转换为字符串，便于修改
        header_str = header.decode('utf-8', errors='ignore')

        # 修改属性名称
        header_str = header_str.replace('property uchar red', 'property uchar diffuse_red')
        header_str = header_str.replace('property uchar green', 'property uchar diffuse_green')
        header_str = header_str.replace('property uchar blue', 'property uchar diffuse_blue')

        # 创建新的头部（用修改后的字符串）
        new_header = header_str.encode('utf-8')

        # 获取数据部分（头部之后的所有内容）
        data = content[header_end + len(b'end_header'):]

        # 将新的头部和数据部分写入新的文件
        with open(output_ply_path, 'wb') as outfile:
            outfile.write(new_header)
            outfile.write(data)

    print(f"PLY 文件已修改并保存为 {output_ply_path}")

# 使用示例
input_ply_path = '/media/zhang-bojun/Linux_D/projects/interSeg3D-Studio-fork/src/backend/object_views/camera_test/scene_with_camera_markers.ply'  # 替换为您的输入文件路径
output_ply_path = '/media/zhang-bojun/Linux_D/projects/interSeg3D-Studio-fork/src/backend/object_views/camera_test/scene_with_camera_markers_dif.ply'  # 替换为您的输出文件路径

modify_ply_colors(input_ply_path, output_ply_path)
