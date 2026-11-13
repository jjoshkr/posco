"""CMY 식용색소 도징 → target color 매칭 시뮬레이터 (전구체 공침 반응기 1단계 실험용).

구성
- config   : 장비/공정 사양 (gamma/X 펌프, MCC 152/118/134, 반응기, 스톡 탱크, 카메라)
- optics   : Beer–Lambert 3×3 모델, RGB↔농도 역산, CIEDE2000
- hardware : MCC 152 → XTR111 → gamma/X, 솔레노이드 밸브, MCC 118/134 모델
- process  : 스톡 탱크, 반응기 물질수지, 교반 혼합 지연
- vision   : RealSense 대역 합성 프레임, 데이터셋 기록기(YOLO 라벨)
- nodes    : I/O 노드(Pi 5 + MCC), AI 노드(Pi 5 + AI HAT+), 노드 간 메시지 버스, 워치독
- control  : 레시피 계획(투입량 계산), 피드포워드 + 카메라 폐루프 트림 제어
- experiment: 시나리오/고장 주입/유량 스윕 실행기
"""
__version__ = "0.1.0"
