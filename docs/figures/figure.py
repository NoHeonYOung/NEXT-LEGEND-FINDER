
import os
import textwrap
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def wrap(text, width=24):
    return "\n".join(textwrap.wrap(text, width=width))


def setup_canvas(title, subtitle=None, figsize=(14, 8)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.text(
        0.02, 0.96, title,
        fontsize=20, fontweight="bold", va="top", ha="left"
    )
    if subtitle:
        ax.text(
            0.02, 0.92, subtitle,
            fontsize=10.5, color="#555555", va="top", ha="left"
        )
    return fig, ax


def add_box(ax, x, y, w, h, title, body="", fc="#F7FAFC", ec="#2B6CB0",
            title_size=12, body_size=9.5, lw=1.8, roundness=0.015):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.01,rounding_size={roundness}",
        linewidth=lw, edgecolor=ec, facecolor=fc
    )
    ax.add_patch(patch)

    ax.text(
        x + 0.015, y + h - 0.03,
        title,
        fontsize=title_size, fontweight="bold",
        va="top", ha="left", color="#1A202C"
    )
    if body:
        ax.text(
            x + 0.015, y + h - 0.07,
            wrap(body, 28),
            fontsize=body_size,
            va="top", ha="left", color="#2D3748"
        )


def add_arrow(ax, x1, y1, x2, y2, text=None, color="#4A5568", lw=1.8):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=14,
        linewidth=lw, color=color
    )
    ax.add_patch(arrow)
    if text:
        ax.text(
            (x1 + x2) / 2,
            (y1 + y2) / 2 + 0.02,
            text,
            fontsize=9.5, color=color,
            ha="center", va="bottom"
        )


def save_svg(fig, filename):
    path = os.path.join(BASE_DIR, filename)
    fig.savefig(path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def figure1_system_overview():
    fig, ax = setup_canvas(
        "Figure 1. System Overview",
        "End-to-end structure of the Next-Legend Finder system."
    )

    add_box(ax, 0.04, 0.63, 0.18, 0.18, "Data Sources",
            "Transfermarkt records, FM-based proxy attributes, user-input qualitative notes",
            fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.28, 0.63, 0.18, 0.18, "Storage Layer",
            "PostgreSQL / Supabase, relational tables, JSONB, pgvector",
            fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.52, 0.63, 0.18, 0.18, "Analysis Layer",
            "Growth Score, strength/weakness analysis, mentality interpretation, mentor matching",
            fc="#FAF5FF", ec="#805AD5")

    add_box(ax, 0.76, 0.63, 0.18, 0.18, "Scenario & Advisory",
            "Career Simulation, qualitative evidence parsing, Gemini advisory support",
            fc="#FFF5F5", ec="#E53E3E")

    add_box(ax, 0.18, 0.28, 0.24, 0.18, "Application Layer",
            "Scouting Board, Player Dossier, Mentor Lab, Career Simulation, Report, Notes",
            fc="#F7FAFC", ec="#4A5568")

    add_box(ax, 0.58, 0.28, 0.24, 0.18, "Persistence Layer",
            "Structured scouting note storage with report sections, simulation result, and evidence snapshots",
            fc="#F7FAFC", ec="#4A5568")

    add_arrow(ax, 0.22, 0.72, 0.28, 0.72)
    add_arrow(ax, 0.46, 0.72, 0.52, 0.72)
    add_arrow(ax, 0.70, 0.72, 0.76, 0.72)

    add_arrow(ax, 0.40, 0.63, 0.30, 0.46, "query & join")
    add_arrow(ax, 0.64, 0.63, 0.70, 0.46, "analysis output")
    add_arrow(ax, 0.42, 0.37, 0.58, 0.37, "save / reload")

    save_svg(fig, "figure1_system_overview.svg")


def figure2_data_pipeline():
    fig, ax = setup_canvas(
        "Figure 2. Data Engineering Pipeline",
        "ETL and analysis-ready data preparation pipeline."
    )

    add_box(ax, 0.05, 0.68, 0.18, 0.16, "Raw CSV Inputs",
            "players.csv, clubs.csv, appearances.csv, valuations.csv, profiles.csv",
            fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.29, 0.68, 0.18, 0.16, "ETL / Cleaning",
            "Schema normalization, type conversion, key mapping, missing-value handling",
            fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.53, 0.68, 0.18, 0.16, "Relational Storage",
            "clubs, players, appearances, player_valuations, player_profiles",
            fc="#FAF5FF", ec="#805AD5")

    add_box(ax, 0.77, 0.68, 0.18, 0.16, "Analysis-Ready State",
            "coverage classification, style_vector availability, FM profile availability",
            fc="#FFF5F5", ec="#E53E3E")

    add_box(ax, 0.18, 0.32, 0.24, 0.18, "Feature Assembly",
            "market value trend, playing time, contribution, age potential, FM attributes, mentality",
            fc="#F7FAFC", ec="#4A5568")

    add_box(ax, 0.58, 0.32, 0.24, 0.18, "Structured Result Storage",
            "simulation_result, env_settings, growth insight, report sections, qualitative evidence",
            fc="#F7FAFC", ec="#4A5568")

    add_arrow(ax, 0.23, 0.76, 0.29, 0.76)
    add_arrow(ax, 0.47, 0.76, 0.53, 0.76)
    add_arrow(ax, 0.71, 0.76, 0.77, 0.76)

    add_arrow(ax, 0.65, 0.68, 0.32, 0.50, "join & assemble")
    add_arrow(ax, 0.42, 0.41, 0.58, 0.41, "analysis output persistence")

    save_svg(fig, "figure2_data_pipeline.svg")


def figure3_growth_score():
    fig, ax = setup_canvas(
        "Figure 3. Growth Score Framework",
        "Weighted rule-based scoring logic for player growth potential."
    )

    add_box(ax, 0.04, 0.60, 0.16, 0.18, "Feature 1",
            "Market value trend\nweight = 30%", fc="#EBF8FF", ec="#3182CE")
    add_box(ax, 0.22, 0.60, 0.16, 0.18, "Feature 2",
            "Playing opportunity\nweight = 20%", fc="#EBF8FF", ec="#3182CE")
    add_box(ax, 0.40, 0.60, 0.16, 0.18, "Feature 3",
            "Contribution\nweight = 15%", fc="#EBF8FF", ec="#3182CE")
    add_box(ax, 0.58, 0.60, 0.16, 0.18, "Feature 4",
            "Age potential\nweight = 15%", fc="#EBF8FF", ec="#3182CE")
    add_box(ax, 0.76, 0.60, 0.16, 0.18, "Feature 5-6",
            "FM attributes + mentality\nweight = 10% + 10%", fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.25, 0.28, 0.22, 0.16, "Weighted Sum",
            "All features normalized to 0~1 and aggregated as a weighted sum",
            fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.56, 0.28, 0.22, 0.16, "Risk Penalty",
            "0~15 point penalty for risky or unreliable conditions",
            fc="#FFF5F5", ec="#E53E3E")

    add_box(ax, 0.36, 0.05, 0.28, 0.12, "Final Score",
            "Growth Score = 100 × weighted_sum − risk_penalty",
            fc="#FAF5FF", ec="#805AD5", title_size=13, body_size=10)

    for x in [0.12, 0.30, 0.48, 0.66, 0.84]:
        add_arrow(ax, x, 0.60, 0.36, 0.44)

    add_arrow(ax, 0.47, 0.36, 0.50, 0.17)
    add_arrow(ax, 0.67, 0.28, 0.57, 0.17)

    save_svg(fig, "figure3_growth_score.svg")


def figure4_mentor_matching():
    fig, ax = setup_canvas(
        "Figure 4. Mentor Matching Framework",
        "Vector-based similarity search and age-aware mentor filtering."
    )

    add_box(ax, 0.06, 0.66, 0.22, 0.18, "Target Prospect",
            "Player with FM proxy profile and 24-dimensional style_vector",
            fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.39, 0.66, 0.22, 0.18, "Similarity Retrieval",
            "pgvector cosine distance search over style_vector embeddings",
            fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.72, 0.66, 0.22, 0.18, "Candidate Pool",
            "Top similar players retrieved from the database",
            fc="#FAF5FF", ec="#805AD5")

    add_box(ax, 0.20, 0.30, 0.24, 0.18, "Age Filtering",
            "Keep sufficiently older candidates; exclude same-age or too-young profiles",
            fc="#FFF5F5", ec="#E53E3E")

    add_box(ax, 0.56, 0.30, 0.24, 0.18, "Final Mentor Set",
            "Present mentor candidates with similarity and explanation",
            fc="#F7FAFC", ec="#4A5568")

    add_arrow(ax, 0.28, 0.75, 0.39, 0.75, "query")
    add_arrow(ax, 0.61, 0.75, 0.72, 0.75, "top-k")
    add_arrow(ax, 0.82, 0.66, 0.68, 0.48, "filter")
    add_arrow(ax, 0.44, 0.39, 0.56, 0.39, "qualified candidates")

    save_svg(fig, "figure4_mentor_matching.svg")


def figure5_career_simulation():
    fig, ax = setup_canvas(
        "Figure 5. Career Simulation Framework",
        "Scenario-based adjustment of growth potential under hypothetical environments."
    )

    add_box(ax, 0.05, 0.66, 0.18, 0.18, "Baseline",
            "Current Growth Score calculated from stored player data",
            fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.28, 0.66, 0.18, 0.18, "Training Intensity",
            "Scenario input from user", fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.51, 0.66, 0.18, 0.18, "Playing Opportunity",
            "Scenario input from user", fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.74, 0.66, 0.18, 0.18, "League Difficulty / Risk",
            "Scenario input from user", fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.24, 0.32, 0.24, 0.18, "Adjustment Model",
            "scenario_adjustment = Δleague × (α × γ × training − β)\nbounded within a safe range",
            fc="#FAF5FF", ec="#805AD5")

    add_box(ax, 0.56, 0.32, 0.24, 0.18, "Final Interpretation",
            "Adjusted score, injury risk, recommended strategy, coaching comments",
            fc="#F7FAFC", ec="#4A5568")

    add_arrow(ax, 0.23, 0.75, 0.24, 0.41)
    add_arrow(ax, 0.37, 0.66, 0.33, 0.50)
    add_arrow(ax, 0.60, 0.66, 0.38, 0.50)
    add_arrow(ax, 0.83, 0.66, 0.43, 0.50)
    add_arrow(ax, 0.48, 0.41, 0.56, 0.41)

    save_svg(fig, "figure5_career_simulation.svg")


def figure6_qualitative_advisory():
    fig, ax = setup_canvas(
        "Figure 6. Qualitative Evidence and Advisory Flow",
        "Optional qualitative evidence is used only for interpretive support."
    )

    add_box(ax, 0.05, 0.67, 0.22, 0.18, "User Qualitative Text",
            "Manual input: article excerpt, interview summary, scouting memo, observation note",
            fc="#EBF8FF", ec="#3182CE")

    add_box(ax, 0.36, 0.67, 0.22, 0.18, "Gemini Signal Extraction",
            "Parse signals related to mentality, risk, trust, development, transfer context",
            fc="#E6FFFA", ec="#319795")

    add_box(ax, 0.67, 0.67, 0.22, 0.18, "Gemini Advisory",
            "Generate supplementary coaching and career guidance",
            fc="#FAF5FF", ec="#805AD5")

    add_box(ax, 0.19, 0.30, 0.24, 0.18, "Structured Storage",
            "qualitative_evidence, gemini_advisory, report sections, input snapshot",
            fc="#F7FAFC", ec="#4A5568")

    add_box(ax, 0.56, 0.30, 0.28, 0.18, "Important Constraint",
            "Gemini does not change Growth Score.\nIt only augments explanations and advisory text.",
            fc="#FFF5F5", ec="#E53E3E")

    add_arrow(ax, 0.27, 0.76, 0.36, 0.76)
    add_arrow(ax, 0.58, 0.76, 0.67, 0.76)
    add_arrow(ax, 0.47, 0.67, 0.31, 0.48, "persist")
    add_arrow(ax, 0.78, 0.67, 0.70, 0.48, "display constraint")

    save_svg(fig, "figure6_qualitative_advisory.svg")


def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    figure1_system_overview()
    figure2_data_pipeline()
    figure3_growth_score()
    figure4_mentor_matching()
    figure5_career_simulation()
    figure6_qualitative_advisory()
    print("All figures generated successfully.")


if __name__ == "__main__":
    main()