import time
import moment
import sift
import cv2
import numpy as np
import argparse
from tqdm import tqdm, trange
from multiprocessing import Pool

from pymongo import MongoClient
from bson.binary import Binary
import pickle
from pathlib import Path
from dynaconf import settings


def prepare_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, required=True)
    parser.add_argument('-d', '--data-path', type=str)
    parser.add_argument('-c', '--collection', type=str)
    return parser


def process_moment_img(img_path):
    res = moment.process_img(img_path, settings.WINDOW.WIN_HEIGHT,
                             settings.WINDOW.WIN_WIDTH)
    res["y_moments"] = Binary(
        pickle.dumps(np.array(res["y_moments"]), protocol=2))
    res["u_moments"] = Binary(
        pickle.dumps(np.array(res["u_moments"]), protocol=2))
    res["v_moments"] = Binary(
        pickle.dumps(np.array(res["v_moments"]), protocol=2))
    return res

def process_sift_img(img_path):
    res = sift.process_img(img_path)
    res['sift'] = Binary(pickle.dumps(res['sift']))
    return res

def build_db(model, data_path, coll_name):
    if data_path is None:
        data_path = Path(settings.DATA_PATH)

    if coll_name is None:
        if model == "moment":
            coll_name = settings.MOMENT.COLLECTION
        elif model == "sift":
            coll_name = settings.SIFT.COLLECTION
        else:
            return

    client = MongoClient(host=settings.HOST,
                         port=settings.PORT,
                         username=settings.USERNAME,
                         password=settings.PASSWORD)
    coll = client.db[coll_name]
    paths = list(data_path.iterdir())

    imgs = []
    p = Pool(processes=10)
    pbar = tqdm(total=len(paths))

    if model == "moment":
        fun = process_moment_img
    elif model == "sift":
        fun = process_sift_img
    else:
        return

    for img in p.imap_unordered(fun, paths):
        imgs.append(img)
        pbar.update()
        if len(imgs) % settings.LOADER.BATCH_SIZE == 0:
            coll.insert_many(imgs)
            imgs.clear()

    if len(imgs) > 0:
        coll.insert_many(imgs)


if __name__ == "__main__":
    parser = prepare_parser()
    args = parser.parse_args()

    if args.data_path:
        path = Path(args.data_path)
        if (not path.exists() or not path.is_dir()):
            raise Exception("Invalid path provided.")
    coll_name = args.collection

    build_db(args.model,
                    None if not args.data_path else path,
                    None if not args.collection else coll_name)
