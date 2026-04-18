"""Generate architecture.png for the ShopWave agent."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

# ── Canvas ──────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(18, 11))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#0d1117")
ax.set_xlim(0, 18)
ax.set_ylim(0, 11)
ax.axis("off")

# ── Helpers ──────────────────────────────────────────────────────────────────
def box(ax, x, y, w, h, fill, edge, text, fontsize=9, text_color="white", bold=False):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.12",
                          linewidth=1.8, edgecolor=edge, facecolor=fill, zorder=3)
    ax.add_patch(rect)
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_color, weight=weight,
            wrap=True, zorder=4,
            multialignment="center")

def section(ax, x, y, w, h, fill, edge, label):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.15",
                          linewidth=2, edgecolor=edge, facecolor=fill,
                          alpha=0.25, zorder=1)
    ax.add_patch(rect)
    ax.text(x + 0.18, y + h - 0.28, label, ha="left", va="top",
            fontsize=8.5, color=edge, weight="bold", zorder=2)

def arrow(ax, x1, y1, x2, y2, color="#aaaaaa", lw=1.5, style="->", label="", dashed=False):
    ls = "--" if dashed else "-"
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                linestyle=ls, connectionstyle="arc3,rad=0.0"),
                zorder=5)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.1, my, label, fontsize=7.5, color=color, va="center", zorder=6)

# ── Title ────────────────────────────────────────────────────────────────────
ax.text(9, 10.65, "ShopWave Support Agent — Architecture",
        ha="center", va="center", fontsize=16, color="white", weight="bold")
ax.text(9, 10.28, "LLM-Orchestrated ReAct Loop  ·  10 LangChain Tools  ·  LangGraph StateGraph",
        ha="center", va="center", fontsize=10, color="#8b949e")

# ── Section backgrounds ──────────────────────────────────────────────────────
section(ax,  0.3, 5.6, 7.2, 4.2,  "#1e2a3a", "#4a9eff", "[ReAct Loop]  LangGraph")
section(ax,  0.3, 1.0, 7.2, 4.3,  "#2a1a2a", "#cc88ff", "[Tools]  10 @tool functions")
section(ax,  8.0, 5.6, 5.3, 4.2,  "#2a2a1a", "#ffcc44", "[State]  AgentState (shared)")
section(ax,  8.0, 1.0, 5.3, 4.3,  "#1a2a1a", "#4aff88", "[Finalize]  finalize_node")
section(ax, 13.6, 1.0, 4.1, 8.8,  "#2a1a1a", "#ff6666", "[Errors]  Error Handling")

# ── START / END ──────────────────────────────────────────────────────────────
box(ax, 2.8, 9.65, 1.8, 0.52, "#238636", "#3fb950", "START", bold=True)
box(ax, 2.8, 5.72, 1.8, 0.52, "#8b0000", "#ff5555", "END",  bold=True)

# ── Agent node ───────────────────────────────────────────────────────────────
box(ax, 0.7, 8.1, 5.8, 1.15, "#1c3a5e", "#4a9eff",
    "agent_node\nClaude  +  bind_tools(ALL_TOOLS)\nDecides which tool to call next",
    fontsize=9, bold=False)

# ── Tool node ────────────────────────────────────────────────────────────────
box(ax, 0.7, 6.5, 5.8, 1.0,  "#2e1f4a", "#cc88ff",
    "tool_node  (LangGraph ToolNode)\nExecutes requested tool calls\nhandle_tool_errors=True",
    fontsize=9)

# ── Arrows: ReAct loop ───────────────────────────────────────────────────────
# START → agent
arrow(ax, 3.7, 9.65, 3.7, 9.27, color="#3fb950", lw=2)
# agent → tools (right side going down)
arrow(ax, 6.0, 8.1, 6.0, 7.5, color="#cc88ff", label="has tool_calls")
# tools → agent (left side going up)
arrow(ax, 0.95, 7.5, 0.95, 8.1, color="#4a9eff", label="ToolMessage results")
# agent → finalize (no tool_calls)
arrow(ax, 3.7, 8.1, 3.7, 7.52, color="#4aff88", label="no tool_calls")
# agent → END (via finalize — drawn below)

# ── Tools grid ───────────────────────────────────────────────────────────────
tools_read = [
    ("get_ticket",              "#1c3558"),
    ("get_customer",            "#1c3558"),
    ("get_customer_orders",     "#1c3558"),
    ("get_order",               "#1c3558"),
    ("get_product",             "#1c3558"),
    ("search_knowledge_base",   "#1c3558"),
    ("check_refund_eligibility","#1c3558"),
]
tools_write = [
    ("issue_refund",  "#3a1e1e"),
    ("escalate",      "#3a1e1e"),
    ("send_reply",    "#3a1e1e"),
]
cols = 4
for i, (name, color) in enumerate(tools_read):
    col, row = i % cols, i // cols
    bx = 0.5 + col * 1.75
    by = 3.85 - row * 0.82
    box(ax, bx, by, 1.65, 0.65, color, "#4a9eff", name, fontsize=7.5)

for i, (name, color) in enumerate(tools_write):
    bx = 0.5 + i * 2.3
    by = 1.18
    box(ax, bx, by, 2.1, 0.65, color, "#ff8844", name, fontsize=7.5)

# Labels inside tool section
ax.text(3.9, 4.62, "Read-Only", fontsize=7.5, color="#4a9eff", ha="center", style="italic")
ax.text(3.9, 1.98, "Write / Action", fontsize=7.5, color="#ff8844", ha="center", style="italic")

# Tool node ↔ tool registry  
arrow(ax, 3.7, 6.5, 3.7, 5.1, color="#cc88ff", lw=1.5, style="<->", label="invoke/result")

# ── AgentState ───────────────────────────────────────────────────────────────
state_fields = (
    "ticket    customer    order\n"
    "product    kb_results    eligibility\n"
    "decision    draft_reply\n"
    "tool_trace    final_status\n"
    "messages  (Annotated list)"
)
box(ax, 8.2, 6.3, 4.9, 3.2, "#1e1e10", "#ffcc44", state_fields, fontsize=8.5)

# ReAct ↔ State
arrow(ax, 6.5, 8.3, 8.2, 8.3, color="#ffcc44", lw=1.5, style="<->", label="read / write")

# ── finalize_node ────────────────────────────────────────────────────────────
finalize_text = (
    "1. Walk message history\n"
    "2. Map tool_call_id → tool_name\n"
    "3. Detect tool errors → log + tag\n"
    "4. Populate: ticket / customer / order\n"
    "   product / kb_results / eligibility\n"
    "5. Set final_status:\n"
    "   refunded | escalated | replied | error\n"
    "6. Extract draft_reply from send_reply"
)
box(ax, 8.2, 1.2, 4.9, 4.1, "#102010", "#4aff88", finalize_text, fontsize=8)

# agent → finalize (down then right)
arrow(ax, 7.5, 8.68, 8.2, 8.68, color="#4aff88", lw=1.5, label="no tool_calls →")
arrow(ax, 10.65, 6.3, 10.65, 5.3, color="#4aff88", lw=1.5)
# finalize → END
arrow(ax, 3.7, 6.22, 3.7, 6.25, color="#ff5555", lw=2)  # placeholder — connect via label
ax.annotate("", xy=(3.7, 6.24), xytext=(8.2, 3.7),
            arrowprops=dict(arrowstyle="->", color="#ff5555", lw=1.5,
                            connectionstyle="arc3,rad=0.3"), zorder=5)
ax.text(5.5, 4.6, "→ END", fontsize=7.5, color="#ff5555")

# ── Error handling column ────────────────────────────────────────────────────
errors = [
    ("AuthenticationError",  "→ 401  Bad API key",         "#cc3333"),
    ("RateLimitError",        "→ 429  Retry after delay",   "#cc7733"),
    ("APIConnectionError",    "→ 503  Network unreachable", "#cc7733"),
    ("APIStatusError",        "→ 502  Upstream API error",  "#cc5533"),
    ("Tool returns error str","→ logged + tagged in trace", "#9933aa"),
    ("recursion_limit = 30",  "→ prevents infinite loop",   "#336699"),
    ("Unexpected Exception",  "→ 500  traceback in logs",   "#993333"),
]
for i, (label, detail, color) in enumerate(errors):
    by = 8.9 - i * 1.12
    box(ax, 13.75, by, 3.75, 0.85, "#1a0808", color,
        f"{label}\n{detail}", fontsize=7.5)

# dashed arrows from agent to error column
arrow(ax, 13.6, 8.68, 13.75, 8.68 + 0.42, color="#ff6666", lw=1, dashed=True)

# ── Legend ───────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(facecolor="#1c3a5e", edgecolor="#4a9eff",  label="LLM node"),
    mpatches.Patch(facecolor="#2e1f4a", edgecolor="#cc88ff",  label="ToolNode"),
    mpatches.Patch(facecolor="#1e1e10", edgecolor="#ffcc44",  label="Shared state"),
    mpatches.Patch(facecolor="#102010", edgecolor="#4aff88",  label="Finalize node"),
    mpatches.Patch(facecolor="#1a0808", edgecolor="#ff6666",  label="Error handling"),
    mpatches.Patch(facecolor="#1c3558", edgecolor="#4a9eff",  label="Read-only tool"),
    mpatches.Patch(facecolor="#3a1e1e", edgecolor="#ff8844",  label="Action tool"),
]
leg = ax.legend(handles=legend_items, loc="lower left", bbox_to_anchor=(0.01, 0.0),
                ncol=7, framealpha=0.2, fontsize=7.5,
                facecolor="#161b22", edgecolor="#30363d",
                labelcolor="white")

# ── Save ─────────────────────────────────────────────────────────────────────
out = "architecture.png"
plt.tight_layout(pad=0.3)
plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {out}")
