import pymem
import pymem.process
import win32gui
import win32con
import time
import os
import imgui
from imgui.integrations.glfw import GlfwRenderer
import glfw
import OpenGL.GL as gl
import requests
import ctypes

WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

esp_rendering = 1
esp_mode = 0
line_rendering = 0
hp_bar_rendering = 1
head_hitbox_rendering = 1

enemy_color = [1.0, 0.0, 0.0, 1.0]     # Red RGBA
teammate_color = [0.0, 0.5, 1.0, 1.0]  # Blue RGBA

offsets = requests.get('https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json').json()
client_dll = requests.get('https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json').json()

dwEntityList = offsets['client.dll']['dwEntityList']
dwLocalPlayerPawn = offsets['client.dll']['dwLocalPlayerPawn']
dwViewMatrix = offsets['client.dll']['dwViewMatrix']

m_iTeamNum = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_iTeamNum']
m_lifeState = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_lifeState']
m_pGameSceneNode = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_pGameSceneNode']
m_modelState = client_dll['client.dll']['classes']['CSkeletonInstance']['fields']['m_modelState']
m_hPlayerPawn = client_dll['client.dll']['classes']['CCSPlayerController']['fields']['m_hPlayerPawn']
m_iHealth = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_iHealth']

print("Waiting for the launch of cs2.exe...")
while True:
    time.sleep(1)
    try:
        pm = pymem.Pymem("cs2.exe")
        client = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
        break
    except:
        pass

print("Starting Scripts!")
os.system("cls")

def w2s(mtx, posx, posy, posz, width, height):
    screenW = (mtx[12] * posx) + (mtx[13] * posy) + (mtx[14] * posz) + mtx[15]
    if screenW > 0.001:
        screenX = (mtx[0] * posx) + (mtx[1] * posy) + (mtx[2] * posz) + mtx[3]
        screenY = (mtx[4] * posx) + (mtx[5] * posy) + (mtx[6] * posz) + mtx[7]
        camX = width / 2
        camY = height / 2
        x = camX + (camX * screenX / screenW)//1
        y = camY - (camY * screenY / screenW)//1
        return [x, y]
    return [-999, -999]

def esp(draw_list):
    if esp_rendering == 0:
        return

    view_matrix = [pm.read_float(client + dwViewMatrix + i * 4) for i in range(16)]
    local_player_pawn_addr = pm.read_longlong(client + dwLocalPlayerPawn)
    try:
        local_player_team = pm.read_int(local_player_pawn_addr + m_iTeamNum)
    except:
        return

    center_x = WINDOW_WIDTH / 2
    center_y = WINDOW_HEIGHT  # bottom center for tracer

    for i in range(64):
        entity = pm.read_longlong(client + dwEntityList)
        if not entity:
            continue

        list_entry = pm.read_longlong(entity + ((8 * (i & 0x7FFF) >> 9) + 16))
        if not list_entry:
            continue

        entity_controller = pm.read_longlong(list_entry + (120) * (i & 0x1FF))
        if not entity_controller:
            continue

        entity_controller_pawn = pm.read_longlong(entity_controller + m_hPlayerPawn)
        if not entity_controller_pawn or entity_controller_pawn == local_player_pawn_addr:
            continue

        list_entry = pm.read_longlong(entity + (0x8 * ((entity_controller_pawn & 0x7FFF) >> 9) + 16))
        if not list_entry:
            continue

        entity_pawn_addr = pm.read_longlong(list_entry + (120) * (entity_controller_pawn & 0x1FF))
        if not entity_pawn_addr or entity_pawn_addr == local_player_pawn_addr:
            continue

        if pm.read_int(entity_pawn_addr + m_lifeState) != 256:
            continue

        entity_team = pm.read_int(entity_pawn_addr + m_iTeamNum)
        is_teammate = entity_team == local_player_team

        if is_teammate and esp_mode == 0:
            continue

        color_values = teammate_color if is_teammate else enemy_color
        color = imgui.get_color_u32_rgba(*color_values)

        game_scene = pm.read_longlong(entity_pawn_addr + m_pGameSceneNode)
        bone_matrix = pm.read_longlong(game_scene + m_modelState + 0x80)

        try:
            # Bone indices
            bones = {
                'head': 6,
                'neck': 5,
                'chest': 4,
                'pelvis': 0,
                'l_shoulder': 13,
                'r_shoulder': 17,
                'l_elbow': 14,
                'r_elbow': 18,
                'l_hand': 15,
                'r_hand': 19,
                'l_knee': 23,
                'r_knee': 26,
                'l_foot': 24,
                'r_foot': 27,
            }

            def get_bone_pos(index):
                base = bone_matrix + index * 0x20
                return (
                    pm.read_float(base),
                    pm.read_float(base + 0x4),
                    pm.read_float(base + 0x8)
                )

            bone_pos_screen = {}
            for name, idx in bones.items():
                x, y, z = get_bone_pos(idx)
                pos2d = w2s(view_matrix, x, y, z, WINDOW_WIDTH, WINDOW_HEIGHT)
                bone_pos_screen[name] = pos2d

            def draw_bone(a, b):
                if -999 in bone_pos_screen[a] or -999 in bone_pos_screen[b]:
                    return
                draw_list.add_line(bone_pos_screen[a][0], bone_pos_screen[a][1],
                                   bone_pos_screen[b][0], bone_pos_screen[b][1],
                                   color, 2.0)

            # Skeleton structure
            draw_bone('head', 'neck')
            draw_bone('neck', 'chest')
            draw_bone('chest', 'pelvis')

            draw_bone('chest', 'l_shoulder')
            draw_bone('chest', 'r_shoulder')
            draw_bone('l_shoulder', 'l_elbow')
            draw_bone('l_elbow', 'l_hand')
            draw_bone('r_shoulder', 'r_elbow')
            draw_bone('r_elbow', 'r_hand')

            draw_bone('pelvis', 'l_knee')
            draw_bone('pelvis', 'r_knee')
            draw_bone('l_knee', 'l_foot')
            draw_bone('r_knee', 'r_foot')

            # Tracer line (bottom center to feet)
            if line_rendering == 1 and -999 not in bone_pos_screen['pelvis']:
                draw_list.add_line(center_x, center_y,
                                   bone_pos_screen['pelvis'][0], bone_pos_screen['pelvis'][1],
                                   color, 1.5)

            # Estimate scale based on head-to-pelvis screen distance
            scale = 1.0
            if -999 not in bone_pos_screen['head'] and -999 not in bone_pos_screen['pelvis']:
                head_y = bone_pos_screen['head'][1]
                pelvis_y = bone_pos_screen['pelvis'][1]
                scale = max(0.5, min(1.8, abs(pelvis_y - head_y) / 150.0))  # clamp to prevent too small/large

            # HP bar near left arm (scaled)
            if hp_bar_rendering == 1 and -999 not in bone_pos_screen['l_shoulder']:
                entity_hp = pm.read_int(entity_pawn_addr + m_iHealth)
                hp_percentage = min(1.0, max(0.0, entity_hp / 100.0))
                x, y = bone_pos_screen['l_shoulder']
                bar_width = 3
                bar_height = 60 * scale  # increase height for better visibility
                top = y - bar_height / 2
                draw_list.add_rect_filled(x - 10, top, x - 10 + bar_width, top + bar_height, imgui.get_color_u32_rgba(0, 0, 0, 0.5))
                draw_list.add_rect_filled(x - 10, top + bar_height * (1 - hp_percentage), x - 10 + bar_width, top + bar_height, color)

            # Head hitbox circle (scaled)
            if head_hitbox_rendering == 1 and -999 not in bone_pos_screen['head']:
                x, y = bone_pos_screen['head']
                draw_list.add_circle_filled(x, y, 8 * scale, color)  # Was 6.5 before

        except:
            continue


menu_visible = False
last_key_state = False

def toggle_menu_state(hwnd, visible):
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if visible:
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style & ~win32con.WS_EX_TRANSPARENT)
    else:
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_TRANSPARENT)

def check_menu_toggle(hwnd):
    global menu_visible, last_key_state
    VK_INSERT = 0x2D
    key_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_INSERT) & 0x8000
    if key_pressed and not last_key_state:
        menu_visible = not menu_visible
        toggle_menu_state(hwnd, menu_visible)
        time.sleep(0.15)
    last_key_state = key_pressed

def main():
    global esp_rendering, esp_mode, line_rendering, hp_bar_rendering, head_hitbox_rendering
    global enemy_color, teammate_color

    if not glfw.init():
        print("Could not initialize OpenGL context")
        exit(1)

    glfw.window_hint(glfw.TRANSPARENT_FRAMEBUFFER, glfw.TRUE)
    window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "cs_overlay", None, None)
    hwnd = glfw.get_win32_window(window)

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME)
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                           win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT)

    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, -2, -2, 0, 0,
                          win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    glfw.make_context_current(window)
    imgui.create_context()
    impl = GlfwRenderer(window)

    while not glfw.window_should_close(window):
        check_menu_toggle(hwnd)

        glfw.poll_events()
        impl.process_inputs()
        imgui.new_frame()

        imgui.set_next_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        imgui.set_next_window_position(0, 0)
        imgui.begin("overlay", flags=imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE |
                    imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_BACKGROUND)
        draw_list = imgui.get_window_draw_list()

        esp(draw_list)

        imgui.end()

        if menu_visible:
            imgui.begin("ESP Menu", True)
            _, esp_rendering = imgui.checkbox("ESP Enabled", esp_rendering)
            _, esp_mode = imgui.checkbox("Show Teammates", esp_mode)
            _, line_rendering = imgui.checkbox("Draw Lines", line_rendering)
            _, hp_bar_rendering = imgui.checkbox("Draw HP Bar", hp_bar_rendering)
            _, head_hitbox_rendering = imgui.checkbox("Draw Head Hitbox", head_hitbox_rendering)

            changed_enemy, new_enemy = imgui.color_edit4("Enemy Color", *enemy_color)
            if changed_enemy:
                enemy_color = list(new_enemy)

            changed_team, new_team = imgui.color_edit4("Teammate Color", *teammate_color)
            if changed_team:
                teammate_color = list(new_team)

            imgui.end()

        imgui.end_frame()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()

if __name__ == '__main__':
    main()
