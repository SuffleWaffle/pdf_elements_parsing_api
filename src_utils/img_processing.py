import io
from src_logging.log_config import setup_logger

logger = setup_logger(__name__)
def delete_objects(img, coords):
    for coord in coords:
        x_min, y_min, x_max, y_max = coord
        img[y_min:y_max, x_min:x_max] = 255
    return img

def convert_pil_image_to_byte_array(img):
    img_byte_array = io.BytesIO()
    img.save(img_byte_array, format='JPEG', subsampling=0, quality=100)
    img_byte_array = img_byte_array.getvalue()
    return img_byte_array

def generate_possible_variants_lines(points, size_y, size_x):
    min_x, max_x, min_y, max_y = points
    variants = [[min_x - 1, max_x - 1, min_y - 1, max_y - 1],
                [min_x + 1, max_x + 1, min_y + 1, max_y + 1],

                [min_x, max_x, min_y + 1, max_y + 1],
                [min_x, max_x, min_y - 1, max_y - 1],

                [min_x + 1, max_x + 1, min_y - 1, max_y - 1],
                [min_x - 1, max_x - 1, min_y + 1, max_y + 1],

                [min_x - 1, max_x - 1, min_y, max_y],
                [min_x + 1, max_x + 1, min_y, max_y],

                [min_x, max_x, min_y, max_y]
                ]

    return [i for i in variants if i[0] > 0 and i[0] < size_x and i[1] > 0 and i[1] < size_x \
            and i[2] > 0 and i[2] < size_y and i[2] > 0 and i[2] < size_y]


def del_by_existence(img_processed, container, tol=0.6):
    to_del = []
    for c, line in enumerate(container):
        try:
            min_x, max_x = min(line[0], line[2]), max(line[0], line[2])
            min_y, max_y = min(line[1], line[3]), max(line[1], line[3])
            variants = generate_possible_variants_lines([min_x, max_x, min_y, max_y],
                                                        size_x=img_processed.shape[1],
                                                        size_y=img_processed.shape[0])
            val = 0
            if min_x == max_x and min_y != max_y:
                val = max([(img_processed[min_y:max_y, min_x] != 255).mean() \
                           for min_x, max_x, min_y, max_y in variants])
            elif min_y == max_y and min_x != max_x:
                val = max([(img_processed[min_y, min_x:max_x] != 255).mean() \
                           for min_x, max_x, min_y, max_y in variants])
            elif min_y != max_y and min_x != max_x:
                val = max([(img_processed[min_y:max_y, min_x:max_x] != 255).mean() \
                           for min_x, max_x, min_y, max_y in variants])

            if val < tol:
                to_del.append(c)
                #logger.info('line')
                #logger.info(line)
                #logger.info(val)
                #logger.info(variants)
                #logger.info('line')

        except Exception as e:
            pass
            #logger.info(f'Exception {e}')

    container = [i for c, i in enumerate(container) if c not in to_del]
    return container

