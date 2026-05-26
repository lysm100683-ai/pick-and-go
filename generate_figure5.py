"""
[ê·¸ë¦¼ 5] Saga ?¨í„´ ?•ìƒ ?ë¦„ ë°??¤íŒ¨ ??ë³´ìƒ ?¸ëžœ??…˜ ?ë¦„???ì„± ?¤í¬ë¦½íŠ¸
- ?ë‹¨: ?•ìƒ ?ë¦„ (Sub1 ??Sub2 ??³µÂ·?™ì†Œ ?±ê³µ ??Sub3 ??Sub4 ??Sub5 ?±ê³µ)
- ?˜ë‹¨: ?¤íŒ¨ ?ë¦„ (Sub2 ??³µ ?±ê³µ ???™ì†Œ ?¤íŒ¨ ??ë³´ìƒ ?¸ëžœ??…˜ ????³µ ì·¨ì†Œ ??Sub5 ?¤íŒ¨)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

plt.rcParams.update({
    'font.family': 'Malgun Gothic',
    'axes.unicode_minus': False,
})

fig, ax = plt.subplots(figsize=(16, 9))
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis('off')

# ?€?€ ?‰ìƒ ?”ë ˆ???€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
C_SUCCESS  = '#2ECC71'   # ì´ˆë¡ (?±ê³µ)
C_FAIL     = '#E74C3C'   # ë¹¨ê°• (?¤íŒ¨)
C_COMPEN   = '#E67E22'   # ì£¼í™© (ë³´ìƒ ?¸ëžœ??…˜)
C_NEUTRAL  = '#5D9CEC'   # ?Œëž‘ (ì¤‘ë¦½ ?¨ê³„)
C_ARROW_OK = '#27AE60'
C_ARROW_NG = '#C0392B'
C_BG_TOP   = '#EAF7EF'   # ?•ìƒ ?ë¦„ ë°°ê²½
C_BG_BOT   = '#FDEDEC'   # ?¤íŒ¨ ?ë¦„ ë°°ê²½
WHITE      = 'white'

# ?€?€ ë°°ê²½ ?ˆì¸ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
top_bg = FancyBboxPatch((0.3, 5.0), 15.4, 3.5,
                         boxstyle='round,pad=0.1',
                         facecolor=C_BG_TOP, edgecolor='#27AE60',
                         linewidth=1.5, zorder=0)
bot_bg = FancyBboxPatch((0.3, 0.4), 15.4, 4.0,
                         boxstyle='round,pad=0.1',
                         facecolor=C_BG_BOT, edgecolor='#C0392B',
                         linewidth=1.5, zorder=0)
ax.add_patch(top_bg)
ax.add_patch(bot_bg)

# ?ˆì¸ ?ˆì´ë¸?ax.text(0.65, 8.25, '?•ìƒ ?ë¦„', fontsize=11, fontweight='bold',
        color='#1E8449', va='center')
ax.text(0.65, 4.15, '?¤íŒ¨ ?ë¦„\n(ë³´ìƒ ?¸ëžœ??…˜)', fontsize=11, fontweight='bold',
        color='#922B21', va='center')

# ?€?€ ë°•ìŠ¤ ê·¸ë¦¬ê¸??¬í¼ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def draw_box(ax, cx, cy, w, h, label, sublabel='', color=C_NEUTRAL,
             fontsize=9.5, text_color='white'):
    box = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                          boxstyle='round,pad=0.1',
                          facecolor=color, edgecolor='#2C3E50',
                          linewidth=1.2, zorder=3)
    ax.add_patch(box)
    if sublabel:
        ax.text(cx, cy + 0.15, label,    ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=text_color, zorder=4)
        ax.text(cx, cy - 0.22, sublabel, ha='center', va='center',
                fontsize=8.0, color=text_color, zorder=4)
    else:
        ax.text(cx, cy, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=text_color, zorder=4)

# ?€?€ ?”ì‚´???¬í¼ ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def draw_arrow(ax, x1, y1, x2, y2, color='#2C3E50', label='',
               connectionstyle='arc3,rad=0.0', lw=1.8):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle='->', color=color, lw=lw,
                    connectionstyle=connectionstyle))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my + 0.18, label, ha='center', va='bottom',
                fontsize=8, color=color, fontweight='bold')

# ?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•
# ?ë‹¨: ?•ìƒ ?ë¦„
# ?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•
Y_TOP = 7.2    # ë©”ì¸ ?ë¦„ y
Y_SUB = 6.0    # ë³‘ë ¬ ?ˆì•½ Sub y (??³µÂ·?™ì†Œ)

# [Sub1] ê²€ì¦?draw_box(ax, 1.5, Y_TOP, 1.6, 0.8, 'Sub 1', '?ˆì•½ ê²€ì¦?, C_NEUTRAL)

# ?”ì‚´??Sub1 ??Sub2
draw_arrow(ax, 2.31, Y_TOP, 3.3, Y_TOP, color=C_ARROW_OK, label='ê²€ì¦??µê³¼')

# [Sub2] ?¸ë? ?ˆì•½ (??³µÂ·?™ì†Œ ë³‘ë ¬) ??ë¶„ê¸° ë°•ìŠ¤
draw_box(ax, 4.0, Y_TOP, 1.6, 0.8, 'Sub 2', 'ë³‘ë ¬ ?ˆì•½', C_NEUTRAL)

# ë¶„ê¸° ?”ì‚´?? Sub2 ????³µ, ?™ì†Œ
draw_arrow(ax, 4.8, Y_TOP + 0.2, 6.5, Y_TOP + 0.6, color=C_ARROW_OK)
draw_arrow(ax, 4.8, Y_TOP - 0.2, 6.5, Y_TOP - 0.6, color=C_ARROW_OK)

# ??³µ ë°•ìŠ¤
draw_box(ax, 7.2, Y_TOP + 0.6, 1.6, 0.65, '????³µ ?ˆì•½', '?±ê³µ', C_SUCCESS)
# ?™ì†Œ ë°•ìŠ¤
draw_box(ax, 7.2, Y_TOP - 0.6, 1.6, 0.65, '?¨ ?™ì†Œ ?ˆì•½', '?±ê³µ', C_SUCCESS)

# ?©ë¥˜ ?”ì‚´????Sub3
draw_arrow(ax, 8.0, Y_TOP + 0.6, 9.0, Y_TOP + 0.15, color=C_ARROW_OK)
draw_arrow(ax, 8.0, Y_TOP - 0.6, 9.0, Y_TOP - 0.15, color=C_ARROW_OK)

# [Sub3] ?•ì •
draw_box(ax, 9.8, Y_TOP, 1.6, 0.8, 'Sub 3', '?ˆì•½ ?•ì •', C_NEUTRAL)

# ?”ì‚´??Sub3 ??Sub4
draw_arrow(ax, 10.6, Y_TOP, 11.55, Y_TOP, color=C_ARROW_OK)

# [Sub4] DB ?€??draw_box(ax, 12.25, Y_TOP, 1.6, 0.8, 'Sub 4', 'DB ?€??, C_NEUTRAL)

# ?”ì‚´??Sub4 ??Sub5
draw_arrow(ax, 13.05, Y_TOP, 14.0, Y_TOP, color=C_ARROW_OK)

# [Sub5] ?±ê³µ ?‘ë‹µ
draw_box(ax, 14.8, Y_TOP, 1.5, 0.8, 'Sub 5', '???±ê³µ ?‘ë‹µ', C_SUCCESS)

# ?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•
# ?˜ë‹¨: ?¤íŒ¨ ?ë¦„ + ë³´ìƒ ?¸ëžœ??…˜
# ?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•?â•
Y_BOT  = 2.7   # ë©”ì¸ ?ë¦„ y
Y_FAIL = 3.6   # ??³µ ?±ê³µ
Y_FAIL2= 1.8   # ?™ì†Œ ?¤íŒ¨

# [Sub1] ê²€ì¦?(?™ì¼)
draw_box(ax, 1.5, Y_BOT, 1.6, 0.8, 'Sub 1', '?ˆì•½ ê²€ì¦?, C_NEUTRAL)
draw_arrow(ax, 2.31, Y_BOT, 3.3, Y_BOT, color=C_ARROW_OK, label='ê²€ì¦??µê³¼')

# [Sub2] ?¸ë? ?ˆì•½
draw_box(ax, 4.0, Y_BOT, 1.6, 0.8, 'Sub 2', 'ë³‘ë ¬ ?ˆì•½', C_NEUTRAL)

# ë¶„ê¸°
draw_arrow(ax, 4.8, Y_BOT + 0.2, 6.5, Y_FAIL, color=C_ARROW_OK)
draw_arrow(ax, 4.8, Y_BOT - 0.2, 6.5, Y_FAIL2, color=C_ARROW_NG)

# ??³µ ?±ê³µ
draw_box(ax, 7.2, Y_FAIL, 1.6, 0.65, '????³µ ?ˆì•½', '?±ê³µ', C_SUCCESS)
# ?™ì†Œ ?¤íŒ¨
draw_box(ax, 7.2, Y_FAIL2, 1.6, 0.65, '?¨ ?™ì†Œ ?ˆì•½', '???¤íŒ¨', C_FAIL)

# ë³´ìƒ ?¸ëžœ??…˜ ë°œë™ ë°•ìŠ¤
draw_box(ax, 9.8, Y_BOT, 2.2, 0.8, '??ë³´ìƒ ?¸ëžœ??…˜ ë°œë™',
         '??³µ ì·¨ì†Œ API ?¸ì¶œ', C_COMPEN, fontsize=8.5)

# ?™ì†Œ ?¤íŒ¨ ??ë³´ìƒ ?¸ëžœ??…˜
draw_arrow(ax, 8.0, Y_FAIL2, 8.9, Y_BOT - 0.3, color=C_ARROW_NG, label='?¤íŒ¨ ê°ì?')
draw_arrow(ax, 8.0, Y_FAIL,  8.9, Y_BOT + 0.3, color=C_ARROW_NG)

# ë³´ìƒ ?¸ëžœ??…˜ ????³µ ì·¨ì†Œ (??°©??êµµì? ?”ì‚´??
ax.annotate('', xy=(7.6, Y_FAIL + 0.2), xytext=(8.9, Y_BOT + 0.25),
            arrowprops=dict(
                arrowstyle='->', color=C_COMPEN, lw=2.0,
                connectionstyle='arc3,rad=-0.35'))
ax.text(7.9, Y_FAIL + 0.78, '?ë™ ì·¨ì†Œ', ha='center', fontsize=8.5,
        color=C_COMPEN, fontweight='bold')

# ??³µ ì·¨ì†Œ ê²°ê³¼ ?œì‹œ
draw_box(ax, 7.2, Y_FAIL + 0.0, 1.6, 0.65, '????³µ ?ˆì•½', '?ë™ ì·¨ì†Œ??, '#AAB7B8',
         text_color='#2C3E50')

# ë³´ìƒ ?¸ëžœ??…˜ ??Sub5 ?¤íŒ¨
draw_arrow(ax, 10.9, Y_BOT, 12.2, Y_BOT, color=C_ARROW_NG)

# [Sub5] ?¤íŒ¨ ?‘ë‹µ
draw_box(ax, 13.2, Y_BOT, 2.0, 0.8, 'Sub 5', '???¤íŒ¨ ?‘ë‹µ\n(retryable=True)', C_FAIL,
         fontsize=8.5)

# ?€?€ ë²”ë? ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
legend_items = [
    mpatches.Patch(facecolor=C_NEUTRAL,  edgecolor='#2C3E50', label='ì²˜ë¦¬ ?¨ê³„ (Sub 1~5)'),
    mpatches.Patch(facecolor=C_SUCCESS,  edgecolor='#2C3E50', label='?±ê³µ'),
    mpatches.Patch(facecolor=C_FAIL,     edgecolor='#2C3E50', label='?¤íŒ¨'),
    mpatches.Patch(facecolor=C_COMPEN,   edgecolor='#2C3E50', label='ë³´ìƒ ?¸ëžœ??…˜'),
]
ax.legend(handles=legend_items, loc='lower right', fontsize=9,
          framealpha=0.9, edgecolor='#95A5A6')

# ?€?€ ?œëª© ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
ax.text(8.0, 8.75, 'Saga ?¨í„´ ?•ìƒ ?ë¦„ ë°??¤íŒ¨ ??ë³´ìƒ ?¸ëžœ??…˜ ?ë¦„??,
        ha='center', va='center', fontsize=14, fontweight='bold', color='#2C3E50')

plt.tight_layout(pad=0.5)

out_path = os.path.join('docs', 'figure5_saga_flowchart.png')
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"[?„ë£Œ] ê·¸ë¦¼ ?€?? {out_path}")
plt.close()
