import argparse
import os

import cv2
import numpy as np
import torch

from model import Generator
from psp_encoder.psp_encoders import PSPEncoder
from utils import ten2cv, cv2ten
import glob
import random
from urllib.request import urlopen
import time
from PIL import Image, ImageOps
import requests
from io import BytesIO

from ffhq_dataset.gen_aligned_image import FaceAlign

seed = 0

random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)


if __name__ == '__main__':
    device = 'cuda'

    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, default='')
    parser.add_argument('--style_selected', type=int, default=0)
    parser.add_argument('--filename', type=str, default=f"{time.time()}.jpg")
    args = parser.parse_args()

    project_path = "/home/alotaima/Projects/side/onlysudo/src/ai/BlendGAN"
    args.size = 1024
    args.ckpt = f'{project_path}/pretrained_models/blendgan.pt'
    args.psp_encoder_ckpt = f'{project_path}/pretrained_models/psp_encoder.pt'
    args.style_img_path = f'{project_path}/test_imgs/style_imgs/'
    args.add_weight_index = 10
    args.outdir = '/src/server/public/ai/style_transfer'
    args.channel_multiplier = 2
    args.latent = 512
    args.n_mlp = 8

    if args.url == '':
        print('Need url or a streamer name!')
        exit()
    
    outdir = args.outdir
    root_path = '/'.join(os.path.abspath(os.getcwd()).split('/')[:-1])
    output_path = f"{root_path}{args.outdir}/{args.filename}"
    style_img_paths = sorted(glob.glob(os.path.join(args.style_img_path, '*.*')))[:]

    print('start')
    fa = FaceAlign()

    checkpoint = torch.load(args.ckpt)
    model_dict = checkpoint['g_ema']

    g_ema = Generator(
        args.size, args.latent, args.n_mlp, channel_multiplier=args.channel_multiplier, load_pretrained_vgg=False
    ).to(device)
    g_ema.load_state_dict(model_dict)
    g_ema.eval()

    psp_encoder = PSPEncoder(args.psp_encoder_ckpt, output_size=args.size).to(device)
    psp_encoder.eval()
    
    response = requests.get(args.url, stream = True)
    img_in = Image.open(BytesIO(response.content)).convert('RGB') 
    img_in = np.array(img_in) 
    img_in = img_in[:, :, ::-1].copy()

    img_in = fa.get_crop_image(img_in)

    img_in_ten = cv2ten(img_in, device)
    img_in = cv2.resize(img_in, (args.size, args.size))

    # img_in = cv2.cvtColor(img_in, cv2.COLOR_BGR2RGB)
    # img_in = Image.fromarray(img_in)
    # img_in = ImageOps.fit(img_in, (args.size, args.size), centering=(0.5, 0.5))
    # img_in = np.array(img_in) 
    # img_in = img_in[:, :, ::-1].copy() 
    
    style_img_paths = sorted(glob.glob(os.path.join(args.style_img_path, '*.*')))[:]
    style_img_path = style_img_paths[args.style_selected]

    name_style = os.path.splitext(os.path.basename(style_img_path))[0]
    img_style = cv2.imread(style_img_path, 1)
    
    img_style_ten = cv2ten(img_style, device)
    img_style = cv2.resize(img_style, (args.size, args.size))

    # img_style = cv2.cvtColor(img_style, cv2.COLOR_BGR2RGB)
    # img_style = Image.fromarray(img_style)
    # img_style = ImageOps.fit(img_style, (args.size, args.size), centering=(0.5, 0.5))
    # img_style = np.array(img_style) 
    # img_style = img_style[:, :, ::-1].copy() 

    with torch.no_grad():
        sample_style = g_ema.get_z_embed(img_style_ten)
        sample_in = psp_encoder(img_in_ten)
        img_out_ten, _ = g_ema([sample_in], z_embed=sample_style, add_weight_index=args.add_weight_index,
                                input_is_latent=True, return_latents=False, randomize_noise=False)
        img_out = ten2cv(img_out_ten)
    
    out = np.concatenate([img_in, img_out], axis=1)
    cv2.imwrite(output_path, out)

    print('Done!')

