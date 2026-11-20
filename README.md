# Esteira IA

Protótipo com ESP32-S3 e câmera OV5640 que conta e classifica peças por cor, mede a altura com um sensor ultrassônico e desvia as rejeitadas com um servo. O painel web mostra o vídeo, as contagens e os ajustes em tempo real.

## Instalação

1. Tenha `make` e `uv` instalados e conecte o ESP32-S3 por USB.
2. Se precisar gravar o MicroPython, execute `make flash` para usar a imagem incluída no repositório. Esse comando apaga a flash da placa.
3. Configure `WIFI_SSID` e `WIFI_PASSWORD` e execute `make upload`. [Configuração](config.py)
4. Abra [esteira.local](http://esteira.local) ou use o IP da página **Rede** no OLED. Se a placa não se conectar ao Wi-Fi, use a rede **Esteira-IA** e a senha definida em `AP_PASSWORD`.

## Pinagem

| Periférico | Ligações |
| --- | --- |
| Câmera OV5640 | Conector da câmera, conforme `CAMERA_PINS` |
| Servo SG90 de rotação contínua (360°) | Sinal no GPIO14 e alimentação de 5 V |
| Buzzer passivo | GPIO46 |
| LED RGB | R no GPIO1, G no GPIO2 e B no GPIO42 |
| Sensor HC-SR04P | TRIG no GPIO47, ECHO no GPIO21 e alimentação de 3,3 V |
| OLED SSD1306 128×32 (I²C `0x3C`) | SCL no GPIO39 e SDA no GPIO38 |
| Botão de emergência | GPIO40 |
| Botão 2 | GPIO41 |

[Configuração dos pinos](config.py) · [Esquemático](esquematico.svg)

## Operação

- No painel web, posicione a linha de contagem e escolha as classes que o servo deve desviar. A opção **IA no navegador** permite classificar por tipo de objeto e requer internet para carregar o modelo.
- Toque no **botão 2** para alternar entre painel, visão e rede no OLED. Mantenha-o pressionado para recalibrar o fundo e o sensor ou para rearmar após uma emergência.
- Acione a parada de emergência pelo botão físico, pelo painel ou pela tecla `Esc`. Ela cancela o ciclo do servo e envia o pulso neutro.

### Calibração do servo

1. Com o braço desacoplado, ajuste **Pulso neutro do servo** até o eixo parar. O valor inicial é 1500 µs.
2. Use **Testar servo** para verificar o sentido. Inverta o sinal de **Variação do pulso no avanço** se precisar trocar o sentido.
3. Monte o braço na posição de repouso e ajuste separadamente o **Tempo de avanço** e o **Tempo de retorno**. O retorno é temporizado e pode variar entre ciclos.

## Modelos 3D

[Base](base.stl) · [Cabeça](cabeca.stl) · [Mastro](mastro.stl) · [Remo](remo.stl)

## Desenvolvimento

Execute `make sim` para abrir o simulador em [localhost:8765](http://localhost:8765). As rotas do painel ficam em [app/api.py](app/api.py).
