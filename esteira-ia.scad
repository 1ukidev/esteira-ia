// Esteira IA: mastro ao lado da esteira com a câmera (ESP32-S3) e o sonar olhando para baixo.
// A base guarda o painel de controle e o servo desviador, e os fios sobem pelo canal do mastro.
// Cada peça é impressa separadamente (escolha em `part`) e presa com parafusos M3:
// os furos de 2,8 mm recebem o parafuso direto, sem porca.

/* [Peça] */
part = "assembly"; // [assembly, base, mast, head, paddle]

/* [Esteira] */
// Largura total da esteira, incluindo a estrutura
belt_width = 120;
// Altura da superfície da esteira em relação à mesa
belt_height = 50;
// Distância da câmera até a esteira
camera_height = 120;
// Comprimento da paleta do servo
paddle_length = 65;

/* [Componentes] */
// Placa ESP32-S3 com a câmera OV5640 (comprimento, largura)
board = [64, 27.5];
sonar_pcb = [45.5, 20.5];
sonar_spacing = 26;
sonar_d = 16;
// SG90: comprimento, largura e altura do corpo
servo_body = [22.8, 12.4, 22.7];
servo_ear_span = 32.4;
servo_hole_spacing = 27.8;
oled_pcb = [27.5, 28];
oled_window = [25, 15];
button_d = 12;
led_d = 5.1;
buzzer_d = 12.4;

/* [Impressão] */
clearance = 0.3;
wall = 2.4;

/* [Hidden] */
$fn = 48;

screw_tap = 2.8;
screw_free = 3.4;

servo_ear_z = 15.9;    // base das abas, medida a partir do fundo do corpo
servo_horn_z = 26.5;   // plano do braço
servo_shaft_offset = 5.5;

top_z = belt_height + camera_height;

// O servo apoia as abas no tampo, então a altura da base deixa o braço 3 mm acima da esteira.
base = [75, 90, belt_height + 3 - (servo_horn_z - servo_ear_z)];
base_x = belt_width / 2 + 3;
roof = 3;
servo_at = [9.5, 30];
socket_at = [22, 0];
socket_depth = 30;
oled_at = [56, -24];
led_at = [48, 6];
buzzer_at = [64, 6];
button_at = [[64, 30], [48, 30]];  // STOP, botão 2

head = [70, 66, 5];
tongue = 25;
ledge = 2.5;
board_pocket = board + [2, 2] * clearance;
sonar_pocket = sonar_pcb + [2, 2] * clearance;
board_y = -head.y / 2 + board_pocket.y / 2 + wall + 0.5;
sonar_y = head.y / 2 - sonar_pocket.y / 2 - wall - 0.5;
head_screw_x = [head.x / 2 + 6, head.x / 2 + tongue - 6];

mast_w = 20;
groove = [10, 12];  // largura e profundidade do canal dos fios
mast_x = base_x + socket_at.x;
mast_bottom = base.z - socket_depth;
mast_h = top_z + head.z + mast_w - mast_bottom;
arm_length = mast_x - head.x / 2;
screw_y = -6;  // fora do canal, onde o mastro é maciço

assert(base.z >= socket_depth + 6, "esteira baixa demais para a base");

module base() {
    socket = [mast_w, mast_w] + [2, 2] * clearance;
    oled = [oled_pcb.y, oled_pcb.x] + [2, 2] * clearance;
    difference() {
        union() {
            difference() {
                translate([0, -base.y / 2, 0]) cube(base);
                translate([wall, -base.y / 2 + wall, -1])
                    cube([base.x - 2 * wall, base.y - 2 * wall, base.z - roof + 1]);
            }
            translate([socket_at.x, socket_at.y, mast_bottom - 3])
                linear_extrude(socket_depth + 3) square(socket + [2, 2] * wall, center = true);
            // Moldura do OLED, aberta do lado dos pinos
            translate([oled_at.x, oled_at.y, base.z - roof - 1.5]) difference() {
                cube([oled.x + 3.2, oled.y + 3.2, 3], center = true);
                cube([oled.x, oled.y, 4], center = true);
                translate([-oled.x / 2, 0, 0]) cube([4, oled.y - 6, 4], center = true);
            }
            translate([buzzer_at.x, buzzer_at.y, base.z - roof - 4]) difference() {
                cylinder(d = buzzer_d + 2.4, h = 4);
                translate([0, 0, -1]) cylinder(d = buzzer_d, h = 6);
            }
        }
        translate([socket_at.x, socket_at.y, mast_bottom])
            linear_extrude(socket_depth + 1) square(socket, center = true);
        // Saída dos fios do canal para dentro da base; o resto do fundo segura o parafuso
        translate([socket_at.x - socket.x / 2, socket_at.y + screw_y + 4, mast_bottom - 4])
            cube([socket.x, socket.y, 5]);
        translate([socket_at.x - groove.x / 2, socket_at.y, mast_bottom - 4])
            cube([groove.x, socket.y, socket_depth - roof]);
        translate([socket_at.x, socket_at.y + screw_y, mast_bottom - 4]) cylinder(d = screw_free, h = 5);

        translate([servo_at.x, servo_at.y, base.z])
            cube([servo_body.y + 2 * clearance, servo_body.x + 2 * clearance, 2 * roof + 1], center = true);
        for (s = [-1, 1])
            translate([servo_at.x, servo_at.y + s * servo_hole_spacing / 2, base.z - roof - 1])
                cylinder(d = 1.8, h = roof + 2);

        translate([oled_at.x, oled_at.y, base.z])
            cube([oled_window.y, oled_window.x, 2 * roof + 1], center = true);
        translate([led_at.x, led_at.y, base.z - roof - 1]) cylinder(d = led_d, h = roof + 2);
        for (p = button_at) translate([p.x, p.y, base.z - roof - 1]) cylinder(d = button_d, h = roof + 2);
        for (dx = [-3, 0, 3], dy = [-3, 0, 3])
            translate([buzzer_at.x + dx, buzzer_at.y + dy, base.z - roof - 1]) cylinder(d = 1.8, h = roof + 2);
    }
}

// Origem no centro do pé do mastro; o braço segue para -X até a cabeça.
module mast() {
    difference() {
        union() {
            translate([-mast_w / 2, -mast_w / 2, 0]) cube([mast_w, mast_w, mast_h]);
            translate([-arm_length, -mast_w / 2, mast_h - mast_w]) cube([arm_length, mast_w, mast_w]);
        }
        translate([-groove.x / 2, mast_w / 2 - groove.y, -1])
            cube([groove.x, groove.y + 1, mast_h - mast_w / 2 + groove.x / 2 + 1]);
        translate([-arm_length - 1, mast_w / 2 - groove.y, mast_h - mast_w / 2 - groove.x / 2])
            cube([arm_length + 1 + groove.x / 2, groove.y + 1, groove.x]);
        translate([0, screw_y, -1]) cylinder(d = screw_tap, h = 13);
        for (x = head_screw_x)
            translate([x - mast_x, screw_y, mast_h - mast_w - 1]) cylinder(d = screw_tap, h = 13);
    }
}

module rim(inner, h) {
    linear_extrude(h) difference() {
        square(inner + [2, 2] * wall, center = true);
        square(inner, center = true);
    }
}

// A placa fica de cabeça para baixo, apoiada nas bordas, com a câmera atravessando a janela.
module camera_window() {
    win = board - [2, 2] * ledge;
    chamfer = 3;
    translate([-win.x / 2, -win.y / 2, -1]) cube([win.x, win.y, head.z + 2]);
    hull() {
        translate([0, 0, -0.01]) linear_extrude(0.01) square(win + [2, 2] * chamfer, center = true);
        translate([0, 0, head.z - 2]) linear_extrude(0.01) square(win, center = true);
    }
    // Passagem do cabo USB-C, do lado oposto ao braço
    translate([-board.x / 2 - 14, -7, -1]) cube([20, 14, head.z + 10]);
}

module sonar_cutout() {
    for (x = [-1, 1] * sonar_spacing / 2)
        translate([x, 0, -1]) cylinder(d = sonar_d + 1, h = head.z + 2);
    // Cristal entre os transdutores
    translate([0, 0, head.z / 2]) cube([10, 12, head.z + 2], center = true);
    // Lado aberto para os pinos
    translate([-sonar_pocket.x / 2, 0, head.z]) cube([sonar_pocket.x, sonar_pocket.y, 10]);
}

module head() {
    tongue_w = mast_w + 2 * clearance + 2 * wall;
    difference() {
        union() {
            translate([-head.x / 2, -head.y / 2, 0]) cube(head);
            translate([head.x / 2 - 1, -tongue_w / 2, 0]) cube([tongue + 1, tongue_w, head.z]);
            // Guias laterais do braço
            for (y = [-1, 1] * (tongue_w - wall) / 2)
                translate([head.x / 2 + tongue / 2, y, head.z + 2]) cube([tongue, wall, 4], center = true);
            translate([0, board_y, head.z]) rim(board_pocket, 4);
            translate([0, sonar_y, head.z]) rim(sonar_pocket, 3);
        }
        for (x = head_screw_x) translate([x, screw_y, -1]) cylinder(d = screw_free, h = head.z + 2);
        translate([0, board_y, 0]) camera_window();
        translate([0, sonar_y, 0]) sonar_cutout();
    }
}

// Encaixa no braço simples do SG90 (rebaixo por baixo) e é presa com os parafusos que vêm com ele.
module paddle() {
    base_t = 3;
    blade = [paddle_length - 7, 2.4, 15];
    difference() {
        union() {
            linear_extrude(base_t) hull() {
                circle(d = 14);
                translate([-17, 0]) circle(d = 8);
                translate([paddle_length, 0]) circle(d = 8);
            }
            translate([7, -blade.y / 2, 0]) cube(blade);
        }
        translate([0, 0, -1]) cylinder(d = 5, h = base_t + 2);
        translate([0, 0, -0.01]) linear_extrude(1.8) hull() {
            circle(d = 7.4);
            translate([-15.5, 0]) circle(d = 4.4);
        }
        for (x = [-9, -13]) translate([x, 0, -1]) cylinder(d = 1.6, h = base_t + 2);
    }
}

module components() {
    color("dimgray", 0.5) translate([-belt_width / 2, -120, belt_height - 8]) cube([belt_width, 240, 8]);

    translate([0, board_y, top_z + head.z]) {
        color("darkgreen") translate([-board.x / 2, -board.y / 2, 0]) cube([board.x, board.y, 1.6]);
        color("black") translate([0, 0, -5]) cylinder(d = 8, h = 5);
    }
    translate([0, sonar_y, top_z + head.z]) {
        color("royalblue") translate([-sonar_pcb.x / 2, -sonar_pcb.y / 2, 0]) cube([sonar_pcb.x, sonar_pcb.y, 1.6]);
        color("silver") for (x = [-1, 1] * sonar_spacing / 2) translate([x, 0, -12]) cylinder(d = sonar_d, h = 12);
    }

    translate([base_x, 0, base.z]) {
        translate([servo_at.x, servo_at.y, 0]) {
            color("deepskyblue") {
                translate([-servo_body.y / 2, -servo_body.x / 2, -servo_ear_z]) cube([servo_body.y, servo_body.x, servo_body.z]);
                translate([-servo_body.y / 2, -servo_ear_span / 2, 0]) cube([servo_body.y, servo_ear_span, 2.5]);
            }
            color("orange") translate([0, servo_shaft_offset, servo_horn_z - servo_ear_z])
                rotate([0, 0, 180]) paddle();
        }
        color("black") translate([oled_at.x - oled_pcb.y / 2, oled_at.y - oled_pcb.x / 2, -roof - 1.6])
            cube([oled_pcb.y, oled_pcb.x, 1.6]);
        color("red") translate([led_at.x, led_at.y, 0]) cylinder(d = 5, h = 3);
        for (i = [0, 1]) color(i == 0 ? "red" : "white")
            translate([button_at[i].x, button_at[i].y, 0]) cylinder(d = button_d - 1, h = 4);
    }
}

module assembly() {
    color("gainsboro") translate([base_x, 0, 0]) base();
    color("lightgray") translate([mast_x, 0, mast_bottom]) mast();
    color("gainsboro") translate([0, 0, top_z]) head();
    components();
}

// Orientações de impressão: sem suportes.
if (part == "assembly") assembly();
else if (part == "base") translate([0, 0, base.z]) rotate([180, 0, 0]) base();
else if (part == "mast") translate([0, 0, mast_w / 2]) rotate([90, 0, 0]) mast();
else if (part == "head") head();
else if (part == "paddle") paddle();
