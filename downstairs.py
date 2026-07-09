# -*- coding: utf-8 -*-
"""小朋友下樓梯（NS-Shaft 式）核心邏輯（純 Python，被 Pyodide 載入瀏覽器執行）。

規則：台階持續向上捲動，角色靠重力下落、←→ 移動；
普通台階回 1 血、尖刺台階扣血（有無敵幀）、彈簧台階反彈、
融化台階踩到後閃爍倒數 MELT_SEC 秒消失（不回血）；
頂部尖刺天花板扣血並下推；掉出畫面底部或血量歸零即死；樓層數＝分數。
捲動速度隨樓層「指數」成長（BASE×GROWTH^floors），到上限後鎖定，等玩家失誤。
架構：每幀 JS 只呼叫一次 step(dt, direction) 再取 state() JSON。
座標：y 向下為正。
測試：tests/test_downstairs.py（19 案例，fail-then-pass 已驗證）。
"""
import json
import random

W, H = 360, 560
PLAYER_W, PLAYER_H = 24.0, 24.0
PLAT_W, PLAT_H = 88.0, 14.0
CEIL_Y = 34.0            # 天花板尖刺底端
MAX_HP = 10
SPIKE_DMG = 3
CEIL_DMG = 3
HEAL = 1
GRAVITY = 1250.0
MOVE_SPEED = 230.0
SPRING_VY = -430.0
CEIL_PUSH_VY = 240.0
IFRAME_SEC = 1.0         # 受傷後無敵秒數
GAP_Y = 92.0             # 台階垂直間距
MELT_SEC = 0.5           # 融化台階：踩到後幾秒消失
SPEED_BASE = 58.0        # 捲動速度指數曲線：BASE × GROWTH^floors，封頂 SPEED_MAX
SPEED_GROWTH = 1.018
SPEED_MAX = 165.0


class Game:
    def __init__(self, rng=None):
        self._rng = rng or random.random
        self.reset()

    def reset(self):
        self.player_x = W / 2 - PLAYER_W / 2
        self.player_y = H * 0.35
        self.player_vy = 0.0
        self.hp = MAX_HP
        self.floors = 0
        self.alive = True
        self.on_ground = False
        self.iframe = 0.0
        self._next_idx = 0
        self.platforms = []      # {"x","y","kind","idx","touched"}
        # 開局：腳下一塊起始台階 + 往下鋪滿
        self._spawn(self.player_x - (PLAT_W - PLAYER_W) / 2, H * 0.35 + PLAYER_H,
                    kind="normal")
        y = H * 0.35 + PLAYER_H + GAP_Y
        while y < H + GAP_Y:
            self._spawn_random(y)
            y += GAP_Y

    # ── 生成 ────────────────────────────────────────────────
    def _spawn(self, x, y, kind):
        self.platforms.append({"x": float(max(0, min(x, W - PLAT_W))), "y": float(y),
                               "kind": kind, "idx": self._next_idx, "touched": False,
                               "melt_t": None})
        self._next_idx += 1

    def _spawn_random(self, y):
        x = self._rng() * (W - PLAT_W)
        r = self._rng()
        if r < 0.55:
            kind = "normal"
        elif r < 0.70:
            kind = "spike"
        elif r < 0.85:
            kind = "spring"
        else:
            kind = "melt"
        self._spawn(x, y, kind)

    # ── 難度曲線（指數成長 → 上限鎖定，等玩家失誤） ─────────
    def scroll_speed(self):
        return min(SPEED_BASE * (SPEED_GROWTH ** self.floors), SPEED_MAX)

    def max_scroll_speed(self):
        return SPEED_MAX

    # ── 傷害 ────────────────────────────────────────────────
    def _damage(self, amount):
        if self.iframe > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.iframe = IFRAME_SEC
        if self.hp == 0:
            self.alive = False

    # ── 主迴圈 ──────────────────────────────────────────────
    def step(self, dt, direction=0):
        """推進一幀。direction ∈ {-1, 0, 1}。"""
        if not self.alive:
            return
        self.iframe = max(0.0, self.iframe - dt)

        # 水平移動＋牆壁夾住
        self.player_x += direction * MOVE_SPEED * dt
        self.player_x = max(0.0, min(self.player_x, W - PLAYER_W))

        # 台階向上捲動＋融化倒數
        v = self.scroll_speed()
        for p in self.platforms:
            p["y"] -= v * dt
            if p["melt_t"] is not None:
                p["melt_t"] -= dt
        self.platforms = [p for p in self.platforms
                          if p["melt_t"] is None or p["melt_t"] > 0]  # 融完即消失

        # 垂直運動與落地判定（用移動前後位置抓「由上而下穿越台階頂」）
        prev_bottom = self.player_y + PLAYER_H
        plat = self._standing_platform(v * dt + 8) if self.on_ground else None
        if plat is not None:
            # 跟著台階上升
            self.player_y = plat["y"] - PLAYER_H
            self.player_vy = 0.0
        else:
            self.on_ground = False
            self.player_vy += GRAVITY * dt
            new_y = self.player_y + self.player_vy * dt
            new_bottom = new_y + PLAYER_H
            landed = None
            if self.player_vy > 0:
                for p in self.platforms:
                    if (p["x"] - PLAYER_W * 0.5 < self.player_x < p["x"] + PLAT_W - PLAYER_W * 0.5
                            and prev_bottom <= p["y"] + v * dt + 1 and new_bottom >= p["y"]):
                        if landed is None or p["y"] < landed["y"]:
                            landed = p
            if landed is not None:
                self._land(landed)
            else:
                self.player_y = new_y

        # 天花板尖刺
        if self.player_y <= CEIL_Y:
            self.player_y = CEIL_Y
            self._damage(CEIL_DMG)
            self.player_vy = CEIL_PUSH_VY
            self.on_ground = False

        # 掉出底部
        if self.player_y > H + PLAYER_H:
            self.alive = False

        # 回收頂部舊台階、底部補新台階
        self.platforms = [p for p in self.platforms if p["y"] > -PLAT_H]
        while max((p["y"] for p in self.platforms), default=0) < H:
            self._spawn_random(max((p["y"] for p in self.platforms), default=H) + GAP_Y)

    def _standing_platform(self, tol):
        """腳下（容差 tol px，涵蓋本幀捲動位移）是否仍有台階。"""
        for p in self.platforms:
            if (p["x"] - PLAYER_W * 0.5 < self.player_x < p["x"] + PLAT_W - PLAYER_W * 0.5
                    and abs((self.player_y + PLAYER_H) - p["y"]) <= tol):
                return p
        return None

    def _land(self, p):
        self.player_y = p["y"] - PLAYER_H
        self.player_vy = 0.0
        kind = p["kind"]
        if kind == "spring":
            self.player_vy = SPRING_VY
            self.on_ground = False
        else:
            self.on_ground = True
            if kind == "spike":
                self._damage(SPIKE_DMG)
            elif kind == "melt":
                if p["melt_t"] is None:
                    p["melt_t"] = MELT_SEC     # 踩到才開始融化，不回血
            elif not p["touched"]:
                self.hp = min(MAX_HP, self.hp + HEAL)
        if not p["touched"]:
            p["touched"] = True
            self.floors = max(self.floors, p["idx"])

    # ── 給前端的狀態 ────────────────────────────────────────
    def state(self):
        return json.dumps({
            "player_x": round(self.player_x, 1),
            "player_y": round(self.player_y, 1),
            "vy": round(self.player_vy, 1),
            "hp": self.hp,
            "floors": self.floors,
            "alive": self.alive,
            "iframe": round(self.iframe, 2),
            "platforms": [{"x": round(p["x"], 1), "y": round(p["y"], 1), "kind": p["kind"],
                           "melt": None if p["melt_t"] is None else round(p["melt_t"], 2)}
                          for p in self.platforms],
        })
