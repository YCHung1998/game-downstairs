# -*- coding: utf-8 -*-
"""小朋友下樓梯（NS-Shaft 式）核心邏輯測試（fail-then-pass：先紅後綠）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from downstairs import (Game, W, H, PLAYER_W, PLAYER_H, CEIL_Y,
                        MAX_HP, SPIKE_DMG, CEIL_DMG)


def seq_rng(values):
    it = iter(values)
    return lambda: next(it)


def make_game(rng_vals=None):
    return Game(rng=seq_rng(rng_vals or [0.5] * 500))


def put_platform(g, x, y, kind="normal", idx=3):
    g.platforms.append({"x": x, "y": y, "kind": kind, "idx": idx, "touched": False})


def drop_player_on(g, plat_x, plat_y, kind="normal", idx=3, frames=90):
    """把玩家放在指定平台正上方自由落下，回傳落地前後紀錄。"""
    put_platform(g, plat_x, plat_y, kind, idx)
    g.player_x = plat_x + 10
    g.player_y = plat_y - 40
    g.player_vy = 0
    for _ in range(frames):
        g.step(1 / 60, direction=0)
        if not g.alive:
            break
    return g


def test_initial_state():
    g = make_game()
    assert g.alive and g.hp == MAX_HP and g.floors == 0
    assert g.platforms                     # 開局就有台階（含腳下起始台階）


def test_gravity_and_landing_on_normal():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, 300, "normal")
    assert g.alive
    assert g.on_ground
    # 站上後貼著台階頂（找回我們放的那塊，refill 會在底部長出新台階）
    plat = next(p for p in g.platforms if p["idx"] == 3)
    assert abs((g.player_y + PLAYER_H) - plat["y"]) < 8


def test_platform_scrolls_up_and_carries_player():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, 400, "normal")
    y1 = g.player_y
    for _ in range(30):
        g.step(1 / 60, direction=0)
    assert g.player_y < y1                 # 站著被往上帶（y 減小）


def test_horizontal_movement_clamped_to_walls():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 150, 400, "normal")
    for _ in range(300):
        g.step(1 / 60, direction=-1)
    assert g.player_x >= 0
    for _ in range(300):
        g.step(1 / 60, direction=1)
    assert g.player_x + PLAYER_W <= W


def test_spike_platform_damages_with_iframes():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, 300, "spike")
    assert g.hp == MAX_HP - SPIKE_DMG      # 落地扣一次
    hp_after = g.hp
    for _ in range(20):                    # 站著不動：無敵幀內不連續扣
        g.step(1 / 60, direction=0)
    assert g.hp == hp_after


def test_spring_bounces_up():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, 300, "spring", frames=40)
    # 落到彈簧後應該有一段向上速度
    assert g.player_vy < 0 or g.player_y < 300 - PLAYER_H


def test_normal_landing_heals_one():
    g = make_game()
    g.platforms = []
    g.hp = 3
    drop_player_on(g, 100, 300, "normal")
    assert g.hp == 4                       # 普通台階回 1 血
    g2 = make_game()
    g2.platforms = []
    g2.hp = MAX_HP
    drop_player_on(g2, 100, 300, "normal")
    assert g2.hp == MAX_HP                 # 不超過上限


def test_ceiling_spikes_damage_and_push_down():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, CEIL_Y + 60, "normal", frames=30)  # 站上高台階（尚未到頂）
    hp0 = g.hp
    for _ in range(240):
        g.step(1 / 60, direction=0)
        if g.hp < hp0:
            break
    assert g.hp == hp0 - CEIL_DMG
    assert g.player_vy > 0 or g.player_y > CEIL_Y   # 被往下推


def test_floor_counting_unique():
    g = make_game()
    g.platforms = []
    drop_player_on(g, 100, 300, "normal", idx=7)
    f1 = g.floors
    for _ in range(10):                    # 站在同一塊上不重複計
        g.step(1 / 60, direction=0)
    assert g.floors == f1 == 7


def test_fall_below_screen_dies():
    g = make_game()
    g.platforms = []                       # 沒有任何台階 → 直接掉出底部
    g.player_y = H - 60
    for _ in range(300):
        g.step(1 / 60, direction=0)
        if not g.alive:
            break
    assert not g.alive


def test_hp_zero_dies():
    g = make_game()
    g.platforms = []
    g.hp = SPIKE_DMG                       # 再踩一次尖刺就歸零
    drop_player_on(g, 100, 300, "spike")
    assert g.hp == 0 and not g.alive


def test_speed_increases_with_depth():
    g = make_game()
    v0 = g.scroll_speed()
    g.floors = 50
    assert g.scroll_speed() > v0
    g.floors = 9999
    assert g.scroll_speed() <= g.max_scroll_speed()


def test_platforms_keep_spawning_below():
    g = make_game()
    for _ in range(600):
        g.step(1 / 60, direction=0)
        if not g.alive:
            break
    ys = [p["y"] for p in g.platforms]
    assert ys and max(ys) > H * 0.5        # 底部持續有新台階補上


def test_state_json_and_reset():
    import json
    g = make_game()
    g.step(1 / 60, direction=1)
    s = json.loads(g.state())
    for key in ("player_x", "player_y", "hp", "floors", "platforms", "alive"):
        assert key in s
    g.hp = 1
    g.alive = False
    g.reset()
    assert g.alive and g.hp == MAX_HP and g.floors == 0
