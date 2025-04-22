import argparse
from src.Blender_mcp import CameraControl  # 假设文件存在

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pos', type=str, default='2,3,1')
    parser.add_argument('--look', type=str, default='0,0,0')
    parser.add_argument('--output', type=str, default='output.png')
    args = parser.parse_args()

    pos = tuple(map(float, args.pos.split(',')))
    look = tuple(map(float, args.look.split(',')))

    cam = CameraControl()
    cam.set_camera_position(pos)
    cam.look_at(look)
    cam.render_to_file(args.output)

if __name__ == '__main__':
    main()
