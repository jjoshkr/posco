# 영상 소스

`posco_turquoise_2030.html`(91초 영상)은 이 폴더의 소스를 합쳐 만든 파일입니다.

- `a2.html`: 헤드, 글꼴, 3D 원근 카메라와 그리기 기본 함수
- `b2.js`, `c2.js`: 지형과 플랜트 설비 모델
- `d2_core.js`, `hud.js`: 렌더러, 색보정, 자막, HUD
- `human09.js`, `hero09.js`: 작업자 인물
- `d3.js`: 홀로그램 장면, `p08v2.js`: 인증 장면
- `tail_p02.js` ~ `tail_p07.js`, `p09v3_*.js`: 장면별 카메라, 효과, HUD
- `p6.js`, `audio_events.js`: Web Audio 사운드
- `video_player.js`: 시간표, 카메라 이동, 전환, 재생 제어

다시 만들기:

    python3 src/build_video.py

(빌드 스크립트는 같은 폴더의 파일을 읽고 저장소 최상위에 `posco_turquoise_2030.html`을 씁니다.)
