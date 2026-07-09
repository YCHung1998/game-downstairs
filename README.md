# 小朋友下樓梯 — Python in the Browser

**🎮 立即遊玩：<https://ychung1998.github.io/game-downstairs/>**

NS-Shaft 式下樓梯。物理、台階生成、血量與樓層計分全部在 `downstairs.py`（純 Python），由 [Pyodide](https://pyodide.org) 在瀏覽器執行；JS 只負責 Canvas 渲染、輸入與音效。

## 怎麼玩

1. 等 2–5 秒 Pyodide 載入後即開始，`←` `→`（或 `A` `D`）移動；手機按住畫面左／右半邊。
2. 台階不斷向上捲，往下踩台階往深處走，**樓層數＝分數**、越深越快。
3. 台階四種：🟫 **普通**（踩到回 1 血）、🔺 **尖刺**（扣 3 血，受傷後短暫無敵）、🟦 **彈簧**（往上彈）、🟧 **融化**（踩到急閃倒數，**0.5 秒**後消失，不回血——當彈板用，別久留）。
4. 頂部尖刺天花板：被捲上去扣 3 血並彈下來。
5. 速度隨樓層**指數**成長（每層 ×1.018），約 58 層後鎖定最高速——之後就是比誰先失誤。
5. 掉出畫面底部或血量歸零即結束；最高樓層存 localStorage；🔊 切音效。

## 本機試玩

```bash
python3 -m http.server 8000   # 開 http://localhost:8000
```

## 跑測試

```bash
python3 -m pytest tests/ -q   # 19 個案例（落地/捲動/傷害/彈簧/融化/計層/死亡/指數速度）
```

## 架構

每幀 JS 只呼叫一次 `game.step(dt, direction)` 再讀 `game.state()` JSON——實測 CPython 0.015ms/幀，Pyodide 最壞估計仍 <1% 幀預算。
