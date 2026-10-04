"""Рисует 10 обликов планеты в PNG (прозрачный фон): python looks.py [папка]"""
import os
import sys

from globe import standalone, LOOKS
from render import Renderer

# долгота, на которую повёрнут каждый облик
LAM = {1: 50, 2: 40, 3: -40, 4: 20, 5: 30, 6: 5, 7: -20, 8: -30, 9: 20, 10: 40}

out = sys.argv[1] if len(sys.argv) > 1 else "looks"
os.makedirs(out, exist_ok=True)
r = Renderer(900, 900)
for k in LOOKS:
    r.shot(standalone(k, LAM[k]), f"{out}/look{k:02d}.png", transparent=True)
    print(k, LOOKS[k])
r.close()
