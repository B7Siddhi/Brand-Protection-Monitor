# Brand Protection Monitor, Day 17: seller network analysis
# Builds a graph linking sellers who share hard-to-fake evidence: the same
# product photo, or word for word identical listing text. Two unrelated
# sellers do not independently produce the same photo or the same paragraph;
# a shared edge is strong evidence they are the same operator running
# multiple accounts, or coordinating deliberately.
#
# Nodes: sellers. Edges: shared_image or copied_description, reusing the
# exact detection logic from S07 and the tuned S08 (day 9's 3-4 seller bound,
# kept here too, for the same reason: wider sharing is boilerplate not a ring).
# Run from the project root:  python3 src/network_analysis.py

import sqlite3
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

con = sqlite3.connect("data/monitor.db")

sellers = pd.read_sql("SELECT seller_id, seller_name FROM sellers", con)
listings = pd.read_sql(
    "SELECT listing_id, seller_id, image_ref, description FROM listings", con)
names = dict(zip(sellers["seller_id"], sellers["seller_name"]))

G = nx.Graph()
G.add_nodes_from(sellers["seller_id"])

def add_edges(groups, reason):
    for _, sids in groups.items():
        sids = sorted(set(sids))
        if 2 <= len(sids) <= 8:  # bounded: wider sharing is boilerplate/coincidence, not a ring
            for i in range(len(sids)):
                for j in range(i + 1, len(sids)):
                    a, b = sids[i], sids[j]
                    if G.has_edge(a, b):
                        G[a][b]["reasons"].add(reason)
                    else:
                        G.add_edge(a, b, reasons={reason})

img_groups = listings[listings["image_ref"].notna()].groupby("image_ref")["seller_id"].apply(list)
add_edges(img_groups, "shared_image")

desc_groups = listings[listings["description"] != ""].groupby("description")["seller_id"].apply(list)
# keep the same 3-4 seller bound tuned on day 9 for copied_description specifically
desc_groups = desc_groups[desc_groups.apply(lambda sids: 3 <= len(set(sids)) <= 4)]
add_edges(desc_groups, "copied_description")

linked = [n for n in G.nodes if G.degree[n] > 0]
G_linked = G.subgraph(linked)
components = sorted(nx.connected_components(G_linked), key=len, reverse=True)

print("NETWORK ANALYSIS RUN")
print(f"  sellers total: {len(sellers)}")
print(f"  sellers with at least one link: {len(linked)}")
print(f"  connected clusters found: {len(components)}")

risk = pd.read_sql(
    "SELECT seller_id, AVG(risk_score) avg_score FROM alerts GROUP BY seller_id", con)
risk_map = dict(zip(risk["seller_id"], risk["avg_score"]))

print("\nCLUSTERS, LARGEST FIRST")
for i, comp in enumerate(components, 1):
    comp = list(comp)
    avg_risk = sum(risk_map.get(s, 0) for s in comp) / len(comp)
    print(f"  cluster {i}: {len(comp)} sellers, avg risk score {avg_risk:.1f}")
    for s in comp:
        print(f"      {names[s]}")

if components:
    top = list(components[0])
    print(f"\nEVIDENCE INSIDE THE LARGEST CLUSTER ({names[top[0]]} and {len(top)-1} others)")
    sub = G_linked.subgraph(top)
    for a, b, data in sub.edges(data=True):
        print(f"  {names[a]:<22} -- {names[b]:<22} linked by {', '.join(data['reasons'])}")

    # visualise the largest cluster
    # Layout: place the tightly linked core (shared_image ring) on a circle,
    # so its many crossing edges read as a clean wheel instead of a tangle,
    # then spread the loosely bridged outsiders below with more room.
    core = {n for n in sub.nodes if any("shared_image" in sub[n][nb]["reasons"] for nb in sub[n])}
    outer = set(sub.nodes) - core
    import math
    pos = {}
    core_list = sorted(core)
    for i, n in enumerate(core_list):
        angle = 2 * math.pi * i / max(len(core_list), 1)
        pos[n] = (2.2 * math.cos(angle), 2.2 * math.sin(angle) + 1.5)
    remaining = nx.spring_layout(sub.subgraph(outer), seed=7, k=2.2, center=(0, -3.2))
    pos.update(remaining)

    fig, ax = plt.subplots(figsize=(13, 11))
    colors, widths = [], []
    for a, b in sub.edges():
        r = sub[a][b]["reasons"]
        is_ring = "shared_image" in r
        colors.append("#1f77b4" if is_ring else "#ff7f0e")
        widths.append(2.2 if is_ring else 1.6)

    nx.draw_networkx_edges(sub, pos, edge_color=colors, width=widths, alpha=0.75, ax=ax)
    nx.draw_networkx_nodes(sub, pos, nodelist=core_list, node_color="#c0392b",
                            node_size=1500, ax=ax, edgecolors="white", linewidths=1.5)
    nx.draw_networkx_nodes(sub, pos, nodelist=sorted(outer), node_color="#2c3e50",
                            node_size=1100, ax=ax, edgecolors="white", linewidths=1.5)

    # labels placed above each node, not squeezed inside it
    for n, (x, y) in pos.items():
        ax.text(x, y + 0.32, names[n], ha="center", va="bottom", fontsize=10,
                 fontweight="bold", color="#111111",
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))

    from matplotlib.lines import Line2D
    legend_items = [
        Line2D([0], [0], color="#1f77b4", lw=2.5, label="shared product image"),
        Line2D([0], [0], color="#ff7f0e", lw=2.5, label="copied description"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#c0392b", markersize=12,
               label="core ring (all linked by shared images)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2c3e50", markersize=12,
               label="loosely bridged, no direct link to the core"),
    ]
    ax.legend(handles=legend_items, loc="lower center", bbox_to_anchor=(0.5, -0.08),
              ncol=2, frameon=False, fontsize=10)
    ax.set_title(f"Largest linked seller cluster ({len(top)} sellers)\n"
                 f"{len(core_list)} form a tight counterfeit ring; {len(outer)} are chained in through one weaker link",
                 fontsize=13)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig("docs/largest_seller_cluster.png", dpi=150, bbox_inches="tight")
    print("\nSaved visualisation to docs/largest_seller_cluster.png")
con.close()
