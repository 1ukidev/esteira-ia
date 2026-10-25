# Esteira IA

Detector de objetos para uma esteira com ESP32-S3, câmera OV5640 e MicroPython. A placa
encontra, rastreia, conta e classifica as peças que cruzam uma linha virtual, mede a altura
delas com o sonar e aciona um servo para desviar as classes rejeitadas. Uma interface web
mostra tudo ao vivo.

## Como funciona

```
OV5640 ─RGB565─► FrameSource ──┬──► JPEG sob demanda ─► /stream ─► navegador ─► COCO-SSD (opcional)
                               │                                                   │ rótulos
                               ▼                                                   ▼
                     Vision (80×60, viper) ──► Tracker ──► App ◄─────────── /api/ai
                     fundo RGB adaptativo      vizinho +    │  ├─ servo desvia rejeitadas
                     + rotulagem de blobs      velocidade   │  ├─ LED RGB, buzzer, OLED
                                                            │  └─ /events (SSE) ──► painel
                                           HC-SR04P ────────┘     altura da peça
```

- **Visão na placa** (`app/kernels.py`): a câmera entrega quadros RGB565 crus (o modo JPEG do
  OV5640 não inicia com este driver), que são reduzidos direto a uma grade de 80×60. O JPEG do
  vídeo só é codificado quando há alguém assistindo. Um modelo de fundo RGB aprende a esteira vazia, compensa variações globais de luz e
  separa o que se move. Os blobs são rotulados por flood fill em código viper, e cada um recebe
  a cor dominante (vermelho, azul, amarelo…). O processamento leva cerca de 18 ms por quadro no S3.
- **Rastreamento** (`app/tracker.py`): associa os blobs entre quadros com predição de velocidade
  e conta cada objeto uma única vez quando ele cruza a linha, no sentido configurado.
- **IA no navegador**: com "IA no navegador" ligado, o painel roda o COCO-SSD (TensorFlow.js)
  sobre o vídeo e envia as detecções à placa. Elas votam no rótulo de cada objeto rastreado, que
  passa a ser contado como "garrafa", "copo", "celular"… em vez de apenas pela cor. O modelo é
  baixado da internet; sem ela, a classificação continua só por cor.
- **Fusão com o sonar**: o HC-SR04P aprende a distância até a esteira vazia e informa a altura de
  cada peça contada. Sem câmera, o sistema vira um contador só por sonar.

## Firmware

O MicroPython genérico não tem driver de câmera. Use o firmware do
[micropython-camera-API](https://github.com/cnadler86/micropython-camera-API/releases), que já
inclui os módulos `camera` e `jpeg`. Baixe `mpy_cam-…-ESP32_GENERIC_S3-SPIRAM_OCT.zip`, extraia o
`firmware.bin` nesta pasta e grave (isso **apaga a flash**):

```bash
make flash FIRMWARE=firmware.bin
```

## Pinagem

Os pinos ficam em [config.py](config.py) e no [esquemático](esquematico.svg). O conector da
câmera ocupa GPIO4–18, que no projeto anterior eram usados por LEDs, buzzer e servo. Os LEDs
amarelo, verde e vermelho foram removidos (o LED RGB faz toda a sinalização), e buzzer e servo
foram movidos:

| Periférico | Original | Atual |
|---|---|---|
| Buzzer passivo | GPIO7 | **GPIO46** |
| Servo SG90 | GPIO15 | **GPIO14** |
| LEDs amarelo, verde e vermelho | GPIO4, 5, 6 | removidos |

Os demais continuam iguais: HC-SR04P (TRIG 47, ECHO 21, alimentado em 3,3 V, sem divisor de
tensão), OLED (SCL 39, SDA 38), LED RGB (1, 2, 42), STOP (40) e botão 2 (41).

## Instalação

1. Coloque o nome e a senha da rede Wi-Fi em `config.py`. Sem rede configurada, ou se a conexão
   falhar, a placa cria o ponto de acesso `Esteira-IA` (senha `esteira123`).
2. Envie o código e reinicie a placa:

   ```bash
   make upload
   ```

3. Abra `http://esteira.local`, ou o IP mostrado no OLED (botão 2 → página "rede").

## Operação

| Elemento | Comportamento |
|---|---|
| LED RGB | ciano respirando: operando · âmbar: objeto em análise · cor da peça após cada contagem · vermelho piscando: rejeição · vermelho pulsando: emergência |
| Buzzer | bipe a cada contagem, tom grave ao rejeitar, sirene no E-STOP |
| Servo | empurra a peça rejeitada (posição, atraso e duração ajustáveis) |
| E-STOP | trava o sistema e recolhe o servo; rearme pelo painel ou pelo botão 2 |
| Botão 2 | toque: troca a página do OLED (painel, visão, rede); segurar: rearma ou recalibra o fundo |
| OLED | contagem, última peça, altura, máscara de movimento ao vivo e dados de rede |

No painel web dá para arrastar a linha de contagem sobre o vídeo, escolher o sentido da esteira,
marcar as classes rejeitadas, ajustar a sensibilidade e o XCLK da câmera (8–24 MHz; a câmera
reinicia e, se a frequência falhar, volta à anterior) e acompanhar as últimas peças com miniaturas
recortadas do vídeo. `Esc` aciona o E-STOP.

## Simulador

Para desenvolver a interface sem a placa, `make sim` executa o controlador, o rastreador e o
servidor reais em CPython, com câmera, sonar e hardware simulados, em `http://localhost:8765`.

## API

| Rota | Descrição |
|---|---|
| `GET /stream` | vídeo MJPEG |
| `GET /snapshot.jpg` | quadro atual |
| `GET /events` | SSE com `state` (5 Hz), `count`, `estop` e `log` |
| `GET /api/state` | estado atual |
| `GET/POST /api/settings` | lê ou altera ajustes (persistidos em `settings.json`) |
| `POST /api/estop` | `{"active": true}` aciona, `{"active": false}` rearma |
| `POST /api/reset` | zera os contadores |
| `POST /api/calibrate` | reaprende o fundo e a distância da esteira |
| `POST /api/ai` | detecções `{label, score, box: [x, y, w, h]}` normalizadas |
| `POST /api/test` | `{"device": "servo" \| "buzzer" \| "count"}` |
