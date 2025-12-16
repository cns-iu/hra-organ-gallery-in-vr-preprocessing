"""
Generate PNG visualizations for heart cell population data
Creates combined-AS charts (with and without legend/titles)
Styled according to HRA Bar Graph Specifications
"""
import pandas as pd
import plotly.graph_objects as go
import os
import sys

# Import config
import config

# Global color mappings per sex
COLOR_MAPS = {}
TOP_CELLS_PER_SEX = {}

def load_filtered_data():
    """Load the filtered heart data"""
    print("📂 Loading filtered data...")
    df = pd.read_csv(config.FILTERED_CSV)
    print(f"   Loaded {len(df):,} rows")
    return df

def extract_as_id(full_url):
    """Extract just the ID from full URL"""
    if pd.isna(full_url):
        return "unknown"
    return full_url.split('/')[-1]

def extract_organ_id(full_url):
    """Extract just the UBERON ID from full organ_id URL"""
    if pd.isna(full_url):
        return "unknown"
    return full_url.split('/')[-1]

def get_ref_organ_id(sex):
    """Get reference organ ID based on sex"""
    return config.REF_ORGAN_ID.get(sex.lower(), "3d-vh-m")

def wrap_label(label, max_length=15):
    """Split long labels into multiple lines"""
    words = label.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) <= max_length:
            current_line = (current_line + " " + word).strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return '<br>'.join(lines)

def build_color_maps_per_sex(df):
    """
    Build separate color mappings for Male and Female.
    Top 9 cell types for each sex get fixed colors.
    """
    color_maps = {}
    top_cells_per_sex = {}
    
    for sex in ['Male', 'Female']:
        df_sex = df[df['sex'] == sex]
        
        # Get top 9 cell types by total cell count for this sex
        top_9 = df_sex.groupby('cell_label')['cell_count'].sum().nlargest(9).index.tolist()
        top_cells_per_sex[sex] = top_9
        
        # Create fixed color mapping
        color_map = {}
        for i, cell_type in enumerate(top_9):
            color_map[cell_type] = config.HRA_COLORS[i]
        color_map['Other'] = config.HRA_COLORS[9]
        
        color_maps[sex] = color_map
        
        print(f"\n🎨 Color Mapping for {sex} (Top 9 + Other):")
        for cell_type, color in color_map.items():
            print(f"   {color} → {cell_type}")
    
    return color_maps, top_cells_per_sex

def apply_chart_styling(fig, title):
    """Apply HRA styling to chart"""
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=28, color=config.TEXT_COLOR, family=config.FONT_FAMILY)
        ),
        width=config.CHART_WIDTH,
        height=config.CHART_HEIGHT,
        paper_bgcolor=config.CHART_BG_COLOR,
        plot_bgcolor=config.CHART_BG_COLOR,
        font=dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        legend=dict(
            font=dict(size=16, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
            bgcolor='rgba(0,0,0,0)'
        )
    )
    
    # X-axis: NO grid lines
    fig.update_xaxes(
        tickfont=dict(size=16, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        titlefont=dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        showgrid=False,
        linecolor=config.BAR_STROKE_COLOR,
        zeroline=False
    )
    
    # Y-axis: horizontal lines only
    fig.update_yaxes(
        tickfont=dict(size=16, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        titlefont=dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        showgrid=True,
        gridcolor='rgba(255,255,255,0.2)',
        gridwidth=1,
        linecolor=config.BAR_STROKE_COLOR,
        zeroline=False
    )
    
    return fig

# def create_single_as_chart(df, tool, sex, as_label, as_id, output_dir):
#     """
#     Create a VERTICAL bar chart for ONE anatomical structure
#     Always shows 9 cell types + Other (10 bars)
#     Legend shows: global top 9 first, then local extras, then Other
#     """
#     global COLOR_MAPS, TOP_CELLS_PER_SEX
#     
#     global_color_map = COLOR_MAPS[sex]
#     global_top_9 = TOP_CELLS_PER_SEX[sex]
#     
#     # Filter for specific tool, sex, and AS
#     df_subset = df[
#         (df['tool'] == tool) & 
#         (df['sex'] == sex) & 
#         (df['as_label'] == as_label)
#     ].copy()
#     
#     if df_subset.empty:
#         print(f"      ⚠️ No data for {as_label}")
#         return None
#     
#     # Get LOCAL top 9 cell types for THIS AS
#     local_top_9 = df_subset.nlargest(9, 'cell_count')['cell_label'].tolist()
#     
#     # Calculate "Other" (sum of everything not in local top 9)
#     df_top9 = df_subset[df_subset['cell_label'].isin(local_top_9)]
#     df_other = df_subset[~df_subset['cell_label'].isin(local_top_9)]
#     other_count = df_other['cell_count'].sum()
#     
#     # Create plot data: local top 9 sorted by count + Other
#     df_plot = df_top9[['cell_label', 'cell_count']].sort_values('cell_count', ascending=False).copy()
#     
#     if other_count > 0:
#         other_row = pd.DataFrame({'cell_label': ['Other'], 'cell_count': [other_count]})
#         df_plot = pd.concat([df_plot, other_row], ignore_index=True)
#     
#     # Multi-line labels
#     df_plot['cell_label_short'] = df_plot['cell_label'].apply(lambda x: wrap_label(x, 12))
#     
#     # Build color mapping for this chart
#     used_colors = set()
#     local_color_map = {}
#     
#     # First: assign fixed colors for global top 9
#     for cell in df_plot['cell_label']:
#         if cell in global_color_map:
#             local_color_map[cell] = global_color_map[cell]
#             used_colors.add(global_color_map[cell])
#     
#     # Second: assign remaining colors to non-global cells
#     available_colors = [c for c in config.HRA_COLORS[:9] if c not in used_colors]
#     color_idx = 0
#     for cell in df_plot['cell_label']:
#         if cell not in local_color_map and cell != 'Other':
#             if color_idx < len(available_colors):
#                 local_color_map[cell] = available_colors[color_idx]
#                 color_idx += 1
#             else:
#                 local_color_map[cell] = config.HRA_COLORS[color_idx % 9]
#                 color_idx += 1
#     
#     local_color_map['Other'] = config.HRA_COLORS[9]
#     
#     # Separate cells into: global top 9 present, local extras, other
#     global_present = [c for c in global_top_9 if c in df_plot['cell_label'].values]
#     local_extras = [c for c in df_plot['cell_label'].values if c not in global_top_9 and c != 'Other']
#     
#     # Legend order: global top 9 first, then local extras, then Other
#     legend_order = global_present + local_extras + ['Other']
#     
#     # Create figure with vertical bars
#     fig = go.Figure()
#     
#     # Add bars in display order (by count), but legend will be ordered differently
#     for _, row in df_plot.iterrows():
#         cell_type = row['cell_label']
#         legend_rank = legend_order.index(cell_type) if cell_type in legend_order else 999
#         
#         fig.add_trace(go.Bar(
#             x=[row['cell_label_short']],
#             y=[row['cell_count']],
#             marker=dict(
#                 color=local_color_map.get(cell_type, config.HRA_COLORS[9]),
#                 line=dict(color=config.BAR_STROKE_COLOR, width=config.BAR_STROKE_WIDTH)
#             ),
#             name=cell_type,
#             showlegend=True,
#             legendrank=legend_rank
#         ))
#     
#     # Apply styling
#     title = f'{wrap_label(as_label, 40)}<br><sup>{tool.capitalize()} | {sex}</sup>'
#     fig = apply_chart_styling(fig, title)
#     
#     fig.update_layout(
#         xaxis_title='Cell Types',
#         yaxis_title='Cell Count',
#         xaxis_tickangle=config.X_AXIS_ANGLE,
#         margin=dict(l=80, r=180, t=100, b=120),
#         legend=dict(
#             orientation='v',
#             yanchor='top',
#             y=1,
#             xanchor='left',
#             x=1.02,
#             traceorder='normal'
#         )
#     )
#     
#     # Generate filename
#     ref_organ_id = get_ref_organ_id(sex)
#     filename = f"{ref_organ_id}--{tool}--{as_id}.png"
#     filepath = os.path.join(output_dir, filename)
#     
#     fig.write_image(filepath, scale=2)
#     print(f"      ✅ {filename}")
#     
#     return filepath

def create_combined_as_chart(df, tool, sex, output_dir, show_legend_and_title=True):
    """
    Create a stacked bar chart with ALL anatomical structures
    Uses fixed color mapping per sex
    
    Args:
        df: DataFrame with filtered data
        tool: Tool name (azimuth, celltypist)
        sex: Sex (Male, Female)
        output_dir: Output directory path
        show_legend_and_title: If True, show legend and title; if False, hide them
    """
    global COLOR_MAPS, TOP_CELLS_PER_SEX
    
    color_map = COLOR_MAPS[sex]
    top_9_cells = TOP_CELLS_PER_SEX[sex]
    
    # Filter for specific tool and sex
    df_subset = df[(df['tool'] == tool) & (df['sex'] == sex)].copy()
    
    if df_subset.empty:
        print(f"   ⚠️ No data for {tool}/{sex}")
        return None
    
    # Get organ_id and organ from the data (should be consistent across rows)
    organ_id_url = df_subset['organ_id'].iloc[0]
    organ_id = extract_organ_id(organ_id_url)
    organ = df_subset['organ'].iloc[0]
    
    # Get AS labels sorted by total cell count
    as_totals = df_subset.groupby('as_label')['cell_count'].sum().sort_values(ascending=False)
    as_order = as_totals.index.tolist()
    as_labels_wrapped = [wrap_label(label, 12) for label in as_order]
    
    # Group cell types
    df_subset['cell_label_grouped'] = df_subset['cell_label'].apply(
        lambda x: x if x in top_9_cells else 'Other'
    )
    
    # Aggregate
    df_agg = df_subset.groupby(['as_label', 'cell_label_grouped'])['cell_count'].sum().reset_index()
    
    # Create figure
    fig = go.Figure()
    
    # Add bars for each cell type (top 9 + Other)
    cell_order = top_9_cells + ['Other']
    for cell_type in cell_order:
        df_cell = df_agg[df_agg['cell_label_grouped'] == cell_type]
        
        cell_counts = []
        for as_label in as_order:
            count = df_cell[df_cell['as_label'] == as_label]['cell_count'].sum()
            cell_counts.append(count)
        
        fig.add_trace(go.Bar(
            name=cell_type,
            x=as_labels_wrapped,
            y=cell_counts,
            marker=dict(
                color=color_map.get(cell_type, config.HRA_COLORS[9]),
                line=dict(color=config.BAR_STROKE_COLOR, width=config.BAR_STROKE_WIDTH)
            ),
            showlegend=show_legend_and_title
        ))
    
    # Apply styling with or without title
    if show_legend_and_title:
        title = f'Anatomical Structures - {tool.capitalize()} - {sex}'
        fig = apply_chart_styling(fig, title)
    else:
        # Apply styling without title
        fig.update_layout(
            width=config.CHART_WIDTH,
            height=config.CHART_HEIGHT,
            paper_bgcolor=config.CHART_BG_COLOR,
            plot_bgcolor=config.CHART_BG_COLOR,
            font=dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY)
        )
    
    # Configure layout
    layout_updates = {
        'barmode': 'stack',
        'xaxis_tickangle': config.X_AXIS_ANGLE,
        'margin': dict(l=80, r=180, t=100, b=120) if show_legend_and_title else dict(l=80, r=80, t=20, b=120)
    }
    
    if show_legend_and_title:
        layout_updates['xaxis_title'] = 'Anatomical Structure'
        layout_updates['yaxis_title'] = 'Cell Count'
        layout_updates['legend'] = dict(
            title=dict(text='Cell Type', font=dict(size=18, color=config.TEXT_COLOR)),
            orientation='v',
            yanchor='top',
            y=1,
            xanchor='left',
            x=1.02
        )
    
    # Update axes styling
    xaxis_params = {
        'tickfont': dict(size=16, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        'showgrid': False,
        'linecolor': config.BAR_STROKE_COLOR,
        'zeroline': False,
        'tickangle': config.X_AXIS_ANGLE,
    }
    if show_legend_and_title:
        xaxis_params['titlefont'] = dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY)
    
    yaxis_params = {
        'tickfont': dict(size=16, color=config.TEXT_COLOR, family=config.FONT_FAMILY),
        'showgrid': True,
        'gridcolor': 'rgba(255,255,255,0.2)',
        'gridwidth': 1,
        'linecolor': config.BAR_STROKE_COLOR,
        'zeroline': False,
    }
    if show_legend_and_title:
        yaxis_params['titlefont'] = dict(size=20, color=config.TEXT_COLOR, family=config.FONT_FAMILY)
    
    fig.update_xaxes(**xaxis_params)
    fig.update_yaxes(**yaxis_params)
    
    fig.update_layout(**layout_updates)
    
    # Generate filename: {ref_organ_id}--{organ_id}--{organ}--{tool}
    ref_organ_id = get_ref_organ_id(sex)
    filename = f"{ref_organ_id}--{organ_id}--{organ}--{tool}.png"
    filepath = os.path.join(output_dir, filename)
    
    fig.write_image(filepath, scale=2)
    print(f"   ✅ {filename}")
    
    return filepath

def main():
    global COLOR_MAPS, TOP_CELLS_PER_SEX
    
    print("=" * 60)
    print("📊 GENERATING PNG VISUALIZATIONS")
    print("=" * 60)
    
    df = load_filtered_data()
    
    # Build color maps PER SEX
    COLOR_MAPS, TOP_CELLS_PER_SEX = build_color_maps_per_sex(df)
    
    # Create output directories
    output_dir_with_legend = os.path.join(config.OUTPUT_DIR, "with_legend")
    output_dir_no_legend = os.path.join(config.OUTPUT_DIR, "no_legend")
    
    os.makedirs(output_dir_with_legend, exist_ok=True)
    os.makedirs(output_dir_no_legend, exist_ok=True)
    
    print(f"\n📁 Output directories:")
    print(f"   With legend/title: {output_dir_with_legend}")
    print(f"   Without legend/title: {output_dir_no_legend}")
    
    tools = df['tool'].unique()
    sexes = df['sex'].unique()
    as_info = df.groupby('as_label')['as'].first().apply(extract_as_id).to_dict()
    
    print(f"\n🔧 Configuration:")
    print(f"   Tools: {tools.tolist()}")
    print(f"   Sexes: {sexes.tolist()}")
    print(f"   Anatomical Structures: {len(as_info)}")
    
    generated_files = []
    
    # Commented out single AS charts
    # print(f"\n" + "=" * 60)
    # print("📈 SINGLE ANATOMICAL STRUCTURE CHARTS")
    # print("=" * 60)
    # 
    # for tool in tools:
    #     for sex in sexes:
    #         print(f"\n   {tool} / {sex}:")
    #         for as_label, as_id in as_info.items():
    #             filepath = create_single_as_chart(df, tool, sex, as_label, as_id, config.OUTPUT_DIR)
    #             if filepath:
    #                 generated_files.append(filepath)
    
    print(f"\n" + "=" * 60)
    print("📈 COMBINED ANATOMICAL STRUCTURE CHARTS (WITH LEGEND/TITLE)")
    print("=" * 60)
    
    for tool in tools:
        for sex in sexes:
            print(f"\n   {tool} / {sex}:")
            filepath = create_combined_as_chart(df, tool, sex, output_dir_with_legend, show_legend_and_title=True)
            if filepath:
                generated_files.append(filepath)
    
    print(f"\n" + "=" * 60)
    print("📈 COMBINED ANATOMICAL STRUCTURE CHARTS (NO LEGEND/TITLE)")
    print("=" * 60)
    
    for tool in tools:
        for sex in sexes:
            print(f"\n   {tool} / {sex}:")
            filepath = create_combined_as_chart(df, tool, sex, output_dir_no_legend, show_legend_and_title=False)
            if filepath:
                generated_files.append(filepath)
    
    print("\n" + "=" * 60)
    print(f"✅ COMPLETE! Generated {len(generated_files)} PNG files")
    print("=" * 60)

if __name__ == "__main__":
    main()
