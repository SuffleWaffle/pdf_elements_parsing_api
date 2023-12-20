import numpy as np
import PIL.Image as pil_image
import cv2
import random


def plot_one_box(img, coord, label=None, color=None, line_thickness=None):
    """
    coord: [x_min, y_min, x_max, y_max] format coordinates.
    img: img to plot on.
    label: str. The label name.
    color: int. color index.
    line_thickness: int. rectangle line thickness.
    """

    tl = line_thickness or int(round(0.0002 * max(img.shape[0:2])))  # line thickness 0.002
    color = color or [random.randint(0, 255) for _ in range(3)]
    c1, c2 = (int(coord[0]), int(coord[1])), (int(coord[2]), int(coord[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl)
    if label:
        tf = max(tl - 1, 1)  # font thickness
        t_size = cv2.getTextSize(label, 0, fontScale=float(tl) / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
        cv2.rectangle(img, c1, c2, color, -1)  # filled
        cv2.putText(img, label, (c1[0], c1[1] - 2), 0, float(tl) / 3, [0, 0, 0], thickness=tf, lineType=cv2.LINE_AA)


def plot_extracted_messages(page, objects_to_draw):
    pix = page.get_pixmap()
    image = pil_image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    image = np.asarray(image)
    for inner_object in objects_to_draw:
        tmp_obj_rect = [inner_object['x0'], inner_object['y0'],
                        inner_object['x1'], inner_object['y1']]

        plot_one_box(image, tmp_obj_rect)
    return image
