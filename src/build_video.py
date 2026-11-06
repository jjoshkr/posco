"""Assemble the single-file 80 s film from the scene sources."""
import re, os
D = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: open(os.path.join(D, f), encoding='utf-8').read()

head = rd('a2.html')
head = head.replace('<title>장면 01 · 시네마틱 전경</title>', '<title>2030 POSCO 청록수소 플랜트</title>')
ui_css = ('<style>\n#start{position:absolute;inset:0;display:flex;flex-direction:column;gap:22px;align-items:center;justify-content:center;background:rgba(5,10,18,.55);z-index:3;font-family:"Pretendard","Noto Sans KR","Malgun Gothic",sans-serif}\n'
          '#start.hide{display:none}#play{font:600 40px "Pretendard","Noto Sans KR","Malgun Gothic",sans-serif;padding:20px 58px;border:1px solid rgba(255,255,255,.7);border-radius:999px;background:rgba(0,68,144,.85);color:#fff;cursor:pointer}\n'
          '#play:disabled{opacity:.45;cursor:default}#load{color:rgba(255,255,255,.8);font:500 22px "Pretendard","Noto Sans KR",sans-serif;min-height:30px}\n'
          '#prog{position:absolute;left:0;right:0;bottom:0;height:6px;background:rgba(255,255,255,.2);z-index:2;cursor:pointer;transition:opacity .5s}#prog.idle{opacity:0}#fill{height:100%;width:0;background:#1BA39C}\n</style>\n')
head = head.replace('</head>', ui_css + '</head>', 1)
head = head.replace('<canvas id="cv"></canvas>', '<canvas id="cv"></canvas>\n<div id="start"><button id="play" disabled>▶ 재생</button><div id="load">장면 준비 중</div></div>\n<div id="prog" class="idle"><div id="fill"></div></div>')
assert 'id="start"' in head

def strip_tail(s):
    i = s.index("addEventListener('resize', render);")
    return s[:i]

def wrap(name, body):
    return f"\nSETUP.{name} = function () {{\n{body}\n}};\n"

parts = [head, rd('b2.js'), rd('c2.js'), rd('d2_core.js'), rd('hud.js'), rd('human09.js'), rd('hero09.js')]
d3 = rd('d3.js')
parts.append('\n' + d3[d3.index('function duskSky'):d3.index("const cv = document.getElementById('cv');")])
p08 = rd('p08v2.js')
parts.append('\n' + p08[:p08.index("const cv = document.getElementById('cv');")])
parts.append('\nconst SETUP = {};\n')
for n, f in [('p02', 'tail_p02.js'), ('p03', 'tail_p03.js'), ('p04', 'tail_p04.js'), ('p05', 'tail_p05.js'), ('p06', 'tail_p06.js'), ('p07', 'tail_p07.js')]:
    parts.append(wrap(n, strip_tail(rd(f))))
p09 = rd('p09v3_a.js') + strip_tail(rd('p09v3_b.js'))
p09 = p09.replace("gm.fillText('안전하게 짓고,', 150, 760); gm.fillText('청정수소 1등급으로', 150, 842);", '')
parts.append(wrap('p09', p09))
# scene-level globals used by the live FX must be visible outside the wrappers
glob = '\nlet REACT_G = null;\n'
parts.append(glob)
# audio engine (old) with new event list
a6 = rd('p6.js')
i0 = a6.index('function buildEvents() {'); i1 = a6.index('// session = one continuous playback run')
a6 = a6[:i0] + rd('audio_events.js') + '\n' + a6[i1:]
a6 = a6.replace("const v0 = T0 < 78.5 ? 1 : clamp(1 - (T0 - 78.5) / 1.5);", "const v0 = T0 < 78.5 ? 1 : Math.max(0, 1 - (T0 - 78.5) / 1.5);")
a6 = a6.replace('T0 < 78.5 ? 1 : Math.max(0, 1 - (T0 - 78.5) / 1.5)', 'T0 < DUR - 1.5 ? 1 : Math.max(0, 1 - (T0 - DUR + 1.5) / 1.5)').replace('if (T0 < 78.5) f.gain.setValueAtTime(1, s.base + 78.5); f.gain.linearRampToValueAtTime(0, s.base + 80);', 'if (T0 < DUR - 1.5) f.gain.setValueAtTime(1, s.base + DUR - 1.5); f.gain.linearRampToValueAtTime(0, s.base + DUR);')
assert '78.5' not in a6 and 's.base + 80' not in a6, 'fade not patched'
parts.append(a6)
parts.append(rd('video_player.js'))
out = '\n'.join(parts)
open('/home/user/posco/posco_turquoise_2030.html', 'w', encoding='utf-8').write(out)
print('ok', len(out))
