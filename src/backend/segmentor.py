from detectron2.utils.logger import setup_logger
setup_logger()

import cv2

from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog

from typing import List

def pre_segment(
        in_paths: List[str]
):
    """
    Pre-segment images using Detectron2's Mask R-CNN model.
    """
    cfg = get_cfg()
    cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5  # set threshold for this model
    cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
    predictor = DefaultPredictor(cfg)

    out_paths = []
    for in_path in in_paths:
        im = cv2.imread(in_path)
        outputs = predictor(im)

        v = Visualizer(im[:, :, ::-1], MetadataCatalog.get(cfg.DATASETS.TRAIN[0]), scale=1.2)
        out = v.draw_instance_predictions(outputs["instances"].to("cpu"))
        out = out.get_image()[:, :, ::-1]
        out_path = in_path.replace('.jpg', '_segmented.jpg')
        cv2.imwrite(out_path, out)
        out_paths.append(out_path)
    return out_paths