import xml.etree.ElementTree as ET
import numpy as np
from math import radians, cos, sin, asin, sqrt
import gpxpy
import folium
import sys
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# python gpx_analyzer.py shinrin.gpx
def haversine(lon1, lat1, lon2, lat2):
    """
    2点間の距離を計算(メートル単位)
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # 地球の半径(メートル)
    return c * r

def create_map(gpx_file_path, output_html='map.html'):
    """
    GPXファイルを読み込み、OpenStreetMap上にルートを赤の実線で描画する
    """
    # GPXファイルを読み込む
    with open(gpx_file_path, 'r', encoding='utf-8') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    # ルートの座標を格納するリスト
    coordinates = []

    # トラックポイントを抽出
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coordinates.append([point.latitude, point.longitude])

    # ルートポイントも抽出（トラックがない場合）
    if not coordinates:
        for route in gpx.routes:
            for point in route.points:
                coordinates.append([point.latitude, point.longitude])

    # ウェイポイントも抽出（他に何もない場合）
    if not coordinates:
        for waypoint in gpx.waypoints:
            coordinates.append([waypoint.latitude, waypoint.longitude])

    if not coordinates:
        print("エラー: GPXファイルに座標データが見つかりませんでした")
        return

    # 地図の中心を計算（全座標の平均）
    center_lat = sum(coord[0] for coord in coordinates) / len(coordinates)
    center_lon = sum(coord[1] for coord in coordinates) / len(coordinates)

    # Foliumで地図を作成
    # 国土地理院の標準地図タイルを使用
    map_object = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png',
        attr='国土地理院',
        dragging=True,
        scroll_wheel_zoom=True,
        zoom_control=True,
        double_click_zoom=True,
        touch_zoom=True,
        box_zoom=True,
        keyboard=True
    )

    # 赤の実線でルートを描画
    folium.PolyLine(
        coordinates,
        color='red',
        weight=3,
        opacity=0.8
    ).add_to(map_object)

    # スタート地点にマーカーを追加
    if coordinates:
        folium.Marker(
            coordinates[0],
            popup='スタート',
            icon=folium.Icon(color='green', icon='play')
        ).add_to(map_object)

        # ゴール地点にマーカーを追加
        if len(coordinates) > 1:
            folium.Marker(
                coordinates[-1],
                popup='ゴール',
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(map_object)

    # HTMLファイルとして保存
    map_object.save(output_html)
    print(f"地図を {output_html} に保存しました")
    print(f"ポイント数: {len(coordinates)}")

def create_interactive_plots(gpx_file_path, output_html='data_plot.html'):
    """
    GPXファイルから速度、心拍数、標高、ケイデンスのインタラクティブなグラフを作成する
    """
    # GPXファイルを解析
    tree = ET.parse(gpx_file_path)
    root = tree.getroot()

    # 名前空間の定義
    ns = {
        'gpx': 'http://www.topografix.com/GPX/1/1',
        'gpxdata': 'http://www.cluetrust.com/XML/GPXDATA/1/0'
    }

    # トラックポイントを抽出
    trackpoints = []
    hrpoints = []
    elevations = []
    cadences = []
    for trkpt in root.findall('.//gpx:trkpt', ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))

        # 標高を抽出
        ele_elem = trkpt.find('gpx:ele', ns)
        ele = float(ele_elem.text) if ele_elem is not None else None

        # 心拍数を抽出
        hr_elem = trkpt.find('.//gpxdata:hr', ns)
        hr = int(hr_elem.text) if hr_elem is not None else None

        # ケイデンスを抽出
        cadence_elem = trkpt.find('.//gpxdata:cadence', ns)
        cadence = int(cadence_elem.text) if cadence_elem is not None else None

        trackpoints.append((lat, lon))
        hrpoints.append(hr)
        elevations.append(ele)
        cadences.append(cadence)

    print(f"トラックポイント数: {len(trackpoints)}")

    # 各ポイント間の距離を計算
    distances = []
    for i in range(1, len(trackpoints)):
        lat1, lon1 = trackpoints[i-1]
        lat2, lon2 = trackpoints[i]
        dist = haversine(lon1, lat1, lon2, lat2)
        distances.append(dist)

    # 累積距離を計算
    cumulative_distance = np.cumsum([0] + distances)

    # サンプリング間隔を1秒と仮定して速度を計算(m/s)
    time_interval = 1.0  # 秒
    speeds = np.array(distances) / time_interval

    # 時間軸を作成
    time = np.arange(len(speeds)) * time_interval

    # 速度をkm/hに変換
    speeds_kmh = speeds * 3.6

    # データの準備
    hr_values = [hr if hr is not None else 0 for hr in hrpoints[1:]]
    ele_values = [ele if ele is not None else 0 for ele in elevations[1:]]
    cadence_values = [cad if cad is not None else 0 for cad in cadences[1:]]

    # 4つのサブプロットを作成
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=('速度 (Velocity)', '心拍数 (Heart Rate)', '標高 (Elevation)', 'ケイデンス (Cadence)'),
        vertical_spacing=0.08,
        shared_xaxes=True  # X軸を共有してズーム・パンを同期
    )

    # 1段目: 速度グラフ
    fig.add_trace(
        go.Scatter(x=time, y=speeds_kmh, mode='lines', name='速度',
                   line=dict(color='#2563eb', width=2)),
        row=1, col=1
    )

    # 2段目: 心拍数グラフ
    fig.add_trace(
        go.Scatter(x=time, y=hr_values, mode='lines', name='心拍数',
                   line=dict(color='#dc2626', width=2)),
        row=2, col=1
    )

    # 3段目: 標高グラフ
    fig.add_trace(
        go.Scatter(x=time, y=ele_values, mode='lines', name='標高',
                   line=dict(color='#16a34a', width=2)),
        row=3, col=1
    )

    # 4段目: ケイデンスグラフ
    fig.add_trace(
        go.Scatter(x=time, y=cadence_values, mode='lines', name='ケイデンス',
                   line=dict(color='#ca8a04', width=2)),
        row=4, col=1
    )

    # 軸ラベルの設定
    fig.update_xaxes(title_text="時間 [s]", row=4, col=1)
    fig.update_yaxes(title_text="速度 [km/h]", row=1, col=1)
    fig.update_yaxes(title_text="心拍数 [bpm]", row=2, col=1)
    fig.update_yaxes(title_text="標高 [m]", row=3, col=1)
    fig.update_yaxes(title_text="ケイデンス [rpm]", row=4, col=1)

    fig.update_yaxes(fixedrange=True)

    # レイアウトの設定
#    fig.update_layout(
#        height=1000,
#        showlegend=False,
#        title_text="GPXデータ分析",
#        hovermode='x unified',  # ホバー時に全グラフの値を表示
#        dragmode='pan'  # デフォルトでパンモード
#    )
    # レイアウトの設定
    fig.update_layout(
        # height=1000,  ← この行を削除（またはコメントアウト）
        autosize=True,   # 枠のサイズに合わせて自動調整
        margin=dict(l=50, r=20, t=50, b=40),  # 余白を少し詰めてグラフを広く表示
        showlegend=False,
        title_text="GPXデータ分析",
        hovermode='x unified',
        dragmode='pan'
    )


    # グリッド線を追加
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

    # 統計情報を表示
    print(f"\n速度の統計情報:")
    print(f"最大速度: {np.max(speeds_kmh):.2f} km/h")
    print(f"平均速度: {np.mean(speeds_kmh):.2f} km/h")
    print(f"最小速度: {np.min(speeds_kmh):.2f} km/h")
    print(f"総距離: {cumulative_distance[-1]/1000:.2f} km")
    print(f"総時間: {time[-1]:.0f} 秒 ({time[-1]/60:.1f} 分)")

    print(f"\n標高の統計情報:")
    print(f"最大標高: {np.max(ele_values):.1f} m")
    print(f"最小標高: {np.min(ele_values):.1f} m")
    print(f"標高差: {np.max(ele_values) - np.min(ele_values):.1f} m")

    print(f"\nケイデンスの統計情報:")
    cadence_nonzero = [c for c in cadence_values if c > 0]
    if cadence_nonzero:
        print(f"平均ケイデンス: {np.mean(cadence_nonzero):.1f} rpm")
        print(f"最大ケイデンス: {np.max(cadence_nonzero):.1f} rpm")

    # HTMLファイルとして保存
    fig.write_html(
        output_html,
        config={'scrollZoom': True, 'responsive': True},
        default_height='100%',
        default_width='100%'
    )
    #fig.write_html(output_html, config={'scrollZoom': True})
    print(f"\nインタラクティブなプロットを '{output_html}' に保存しました")

    return fig

def create_combined_view(gpx_file_path, output_html='gpx_analysis.html'):
    """
    地図とグラフを1つのHTMLファイルに統合する
    """
    import os

    # 出力HTMLと同じディレクトリに一時ファイルを作成
    output_dir = os.path.dirname(output_html) if os.path.dirname(output_html) else '.'
    base_name = os.path.splitext(os.path.basename(output_html))[0]

    map_temp = os.path.join(output_dir, f'{base_name}_map.html')
    plot_temp = os.path.join(output_dir, f'{base_name}_plot.html')

    # 地図を作成
    create_map(gpx_file_path, map_temp)

    # グラフを作成
    create_interactive_plots(gpx_file_path, plot_temp)

    # 統合HTMLを作成（両方をiframeで表示）
    combined_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPXデータ分析 - 地図とグラフ</title>

    <style>
        /* 印刷時のページ設定をA4横向きに指定 */
        @page {{
            size: A4 landscape;
            margin: 0;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background-color: #e5e7eb;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        /* A4横向き（297mm × 210mm）のコンテナ */
        .container {{
            display: flex;
            flex-direction: column;
            width: 297mm;
            height: 210mm;
            background-color: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 15px;
            flex-shrink: 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 18px;
            font-weight: 600;
        }}
        .info {{
            padding: 5px 15px;
            background-color: #e0e7ff;
            border-bottom: 1px solid #c7d2fe;
            font-size: 11px;
            color: #4338ca;
            flex-shrink: 0;
        }}
        .content {{
            display: flex;
            flex: 1;
            overflow: hidden;
            min-height: 0;
        }}
        .map-container {{
            flex: 1;
            position: relative;
            border-right: 2px solid #ddd;
        }}
        .plot-container {{
            flex: 1.2; /* グラフ側を少し広めに確保 */
            position: relative;
            background-color: white;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: none;
            display: block;
        }}
        .section-title {{
            position: absolute;
            top: 8px;
            left: 8px;
            background-color: rgba(255, 255, 255, 0.9);
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            color: #333;
            box-shadow: 0 1px 4px rgba(0,0,0,0.15);
            z-index: 1000;
            pointer-events: none;
        }}
        /* 印刷時の調整 */
        @media print {{
            body {{
                background-color: white;
                display: block;
            }}
            .container {{
                box-shadow: none;
                width: 297mm;
                height: 210mm;
            }}
            .info {{
                display: none; /* 印刷時は操作説明バーを非表示にしてグラフを広くする */
            }}
        }}
    </style>   
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚴 GPXデータ分析</h1>
        </div>
        <div class="info">
            <strong>📍 操作方法:</strong>
            地図: ドラッグで移動、マウスホイールでズーム |
            グラフ: ドラッグでパン、マウスホイールでズーム、ダブルクリックでリセット、ホバーで詳細表示
        </div>
        <div class="content">
            <div class="map-container">
                <div class="section-title">📍 ルート地図</div>
                <iframe src="{os.path.basename(map_temp)}"></iframe>
            </div>
            <div class="plot-container">
                <div class="section-title">📊 データグラフ</div>
                <iframe src="{os.path.basename(plot_temp)}"></iframe>
            </div>
        </div>
    </div>
</body>
</html>"""

    # 統合HTMLを保存
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(combined_html)

    print(f"\n✅ 統合ビューを '{output_html}' に保存しました")
    print(f"   - 地図: {map_temp}")
    print(f"   - グラフ: {plot_temp}")
    print(f"\n💡 ヒント: 3つのファイルは同じフォルダに保存してください")

def main():
    """
    GPXファイルを解析して地図とデータグラフを作成する
    """
    if len(sys.argv) < 2:
        print("使用方法: python gpx_analyzer.py <gpxファイルパス> [出力HTMLファイル名]")
        print("例: python gpx_analyzer.py shinrin.gpx")
        print("例: python gpx_analyzer.py shinrin.gpx gpx_analysis.html")
        sys.exit(1)

    gpx_path = sys.argv[1]
    output_html = sys.argv[2] if len(sys.argv) > 2 else 'gpx_analysis.html'

    print(f"GPXファイルを解析中: {gpx_path}")
    print("=" * 60)

    # 地図とグラフを統合したHTMLを作成
    print("\n地図とグラフを作成中...")
    create_combined_view(gpx_path, output_html)

    print("\n" + "=" * 60)
    print("解析完了!")
    print(f"\nブラウザで '{output_html}' を開いてください。")

if __name__ == '__main__':
    main()
