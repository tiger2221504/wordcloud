import os
import io
import re
import json
import uuid
import secrets
from datetime import datetime, timezone, timedelta
import streamlit as st
from janome.tokenizer import Tokenizer
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from streamlit_cookies_manager import EncryptedCookieManager

# =========================================================
#ページコンフィグ
# =========================================================
st.set_page_config(
     page_title="ワードクラウドジェネレーター",
     page_icon="☁️",
     initial_sidebar_state="collapsed",
     menu_items={
         'About': """
         ワードクラウドの作成ができます(日本語対応)
         """
     }
 )

# =========================================================
# 先に初期化
# =========================================================
st.session_state.setdefault("last_png", None)
st.session_state.setdefault("last_config", None)
st.session_state.setdefault("confirm_action", None)
st.session_state.setdefault("wc_seed", None)

# =========================================================
# Cookieで内容保存
# =========================================================
JST = timezone(timedelta(hours=9))

HISTORY_COOKIE_KEY = "history_v1"
MAX_HISTORY = 10  # cookie容量の都合で多すぎないように
COOKIE_PASSWORD = os.getenv("WORDCLOUD_COOKIE_PASSWORD", "change-me-please")

cookies = EncryptedCookieManager(prefix="wordcloud_", password=COOKIE_PASSWORD)
if not cookies.ready():
    # cookieが準備できるまで待つ
    st.stop()


def _now_iso_jst():
    return datetime.now(JST).isoformat(timespec="seconds")


def load_history():
    raw = cookies.get(HISTORY_COOKIE_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_history(history):
    # cookieは容量制限が厳しい（一般に 4KB 程度）ので、保存件数を制限しつつ
    # それでも大きすぎる場合はエラーにする。
    history = history[-MAX_HISTORY:]
    raw = json.dumps(history, ensure_ascii=False, separators=(",", ":"))

    # EncryptedCookieManagerは暗号化・エンコードでさらに増えるので少し余裕を見てチェック
    if len(raw.encode("utf-8")) > 2800:
        raise ValueError(
            "保存データが大きすぎます。"
            "（テキストを短くする／保存件数を減らす などで調整してください）"
        )

    cookies[HISTORY_COOKIE_KEY] = raw
    cookies.save()


def delete_history_item(item_id: str):
    history = load_history()
    new_history = [x for x in history if x.get("id") != item_id]
    save_history(new_history)


def reset_history():
    cookies[HISTORY_COOKIE_KEY] = json.dumps([], ensure_ascii=False)
    cookies.save()


# =========================================================
# 復元用関数
# =========================================================
def apply_config_to_inputs(cfg: dict):
    st.session_state["wc_text"] = cfg.get("text", "")
    st.session_state["wc_priority_nouns_input"] = cfg.get("priority_nouns_input", "")
    st.session_state["wc_exclude_input"] = cfg.get("exclude_input", "")
    st.session_state["wc_selected_pos"] = cfg.get("selected_pos", ["名詞"])
    st.session_state["wc_max_words"] = int(cfg.get("max_words", 50))
    st.session_state["wc_min_font_size"] = int(cfg.get("min_font_size", 10))
    st.session_state["wc_width"] = int(cfg.get("width", 800))
    st.session_state["wc_height"] = int(cfg.get("height", 600))
    st.session_state["wc_collocations"] = bool(cfg.get("collocations", True))
    st.session_state["wc_background_color"] = cfg.get("background_color", "#f4f5f7")
    st.session_state["wc_colormap"] = cfg.get("colormap", "viridis")
    st.session_state["wc_seed"] = cfg.get("seed")

    # 直前の生成結果を消す場合↓
    st.session_state["last_png"] = None
    st.session_state["last_config"] = None



# =========================================================
# 形態素処理
# =========================================================
def apply_priority_nouns(text, priority_nouns):
    """
    priority_nounsを最優先で1語として扱うため、
    文字列中の該当箇所をプレースホルダに置換してからJanomeに渡す。
    """

    if not priority_nouns:
        return text, {}

    uniq = sorted(set([w for w in priority_nouns if w]), key=len, reverse=True)
    if not uniq:
        return text, {}

    # BMP Private Use Area: U+E000 .. U+F8FF (6400文字)
    PUA_START = 0xE000
    PUA_END = 0xF8FF
    if len(uniq) > (PUA_END - PUA_START + 1):
        raise ValueError("priority_nouns が多すぎます（最大6400語まで）")

    word_to_ph = {}
    ph_to_word = {}
    for i, w in enumerate(uniq):
        ph = chr(PUA_START + i)  # 1文字プレースホルダ
        word_to_ph[w] = ph
        ph_to_word[ph] = w

    pattern = re.compile("|".join(map(re.escape, uniq)))

    def repl(m):
        w = m.group(0)
        ph = word_to_ph[w]
        return f" {ph} "  # 空白で分離

    replaced = pattern.sub(repl, text)
    return replaced, ph_to_word

def tokenize_japanese(text, selected_pos, exclude_words=None, priority_nouns=None):
    tokenizer = Tokenizer()

    if exclude_words is None:
        exclude_words = []
    if priority_nouns is None:
        priority_nouns = []

    # 名詞リストを最優先で1語化
    text_for_tokenize, ph_to_word = apply_priority_nouns(text, priority_nouns)

    tokens = tokenizer.tokenize(text_for_tokenize)

    words = []
    for token in tokens:
        surface = token.surface

        # 置換したプレースホルダは「名詞」として扱う
        if surface in ph_to_word:
            word = ph_to_word[surface]
            pos_major = '名詞'
        else:
            # Janomeのbase_formが'*'の場合はsurfaceを使う
            base = token.base_form
            word = base if base != '*' else surface
            pos_major = token.part_of_speech.split(',')[0]

        if pos_major in selected_pos and word not in exclude_words and len(word) > 1:
            words.append(word)

    return ' '.join(words)

def generate_wordcloud(
    text,
    width,
    height,
    background_color,
    font_path,
    selected_pos,
    exclude_words=None,
    priority_nouns=None,
    max_words=50,
    collocations=False,
    min_font_size=10,
    colormap=None,
    random_state=None
):
    horizontal = 0.5
    if collocations:
        horizontal = 1.0

    words = tokenize_japanese(text, selected_pos, exclude_words, priority_nouns)

    # デバッグ用出力
    print("トークナイズ後の単語列:", words)

    wordcloud = WordCloud(
        font_path=font_path,
        width=width,
        height=height,
        background_color=background_color,
        max_words=max_words,
        min_font_size=min_font_size,
        collocations=collocations,
        colormap=colormap,
        prefer_horizontal=horizontal,
        random_state=random_state,
    ).generate(words)

    return wordcloud

def render_wordcloud_to_png_bytes(wordcloud):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf.getvalue()


# =========================================================
# UI
# =========================================================

# Streamlitアプリのタイトル
st.title("ワードクラウドジェネレーター☁️")

# ユーザーからのテキスト入力
user_input = st.text_area(
    "テキストを入力してください",
    key="wc_text"
)

# 名詞リスト
priority_nouns_input = st.text_input(
    "名詞として優先したい単語を入力してください（カンマ区切り）",
    value="",
    key="wc_priority_nouns_input"
)
priority_nouns = [w.strip() for w in priority_nouns_input.split(',') if w.strip()]

# 除外する単語の入力
exclude_input = st.text_input(
    "除外する単語を入力してください（カンマ区切り）",
    value="的, こと, もの, それ, これ, ため, よう, そこ, どこ, とき, あと, みたい, ような",
    key="wc_exclude_input"
)

# 除外単語をリストに変換
exclude_words = [word.strip() for word in exclude_input.split(',') if word.strip()]

# 品詞のオプション
pos_options = [
    '名詞',    # Noun
    '動詞',    # Verb
    '形容詞',  # Adjective
    '副詞',    # Adverb
    '助詞',    # Particle
    '助動詞',  # Auxiliary verb
    '連体詞',  # Adnominal adjective
    '接続詞',  # Conjunction
    '感動詞',  # Interjection
    '記号',    # Symbol
    'その他'   # Other
]

# 品詞選択のマルチセレクトウィジェット
selected_pos = st.multiselect(
    "ワードクラウドに含める品詞を選択してください",
    options=pos_options,
    default=['名詞'],  # デフォルト選択
    key="wc_selected_pos"
)

# 表示する単語数の上限
max_words = st.number_input(
    "表示する最大単語数",
    min_value=5,
    max_value=200,
    value=50,
    step=1,
    key="wc_max_words"
)

# 最小フォントサイズ
min_font_size = st.number_input(
    "最小フォントサイズ",
    min_value=1,
    max_value=100,
    value=10,
    step=1,
    key="wc_min_font_size"
)

# ワードクラウド画像の幅入力
width = st.number_input(
    "ワードクラウドの幅",
    min_value=100,
    max_value=4000,
    value=800,
    step=1,
    key="wc_width"
)

# ワードクラウド画像の高さ入力
height = st.number_input(
    "ワードクラウドの高さ",
    min_value=100,
    max_value=4000,
    value=600,
    step=1,
    key="wc_height"
)

# 横書きのみ
collocations = st.checkbox(
    "横書きのみ",
    value=True,
    key="wc_collocations"
)

# 背景色の選択
background_color = st.color_picker(
    "背景色を選択", "#f4f5f7",
    key="wc_background_color"
)

# カラーマップの選択
colormaps_list = [
    "viridis","cividis",  "inferno", "magma", "plasma", "summer",
    "Accent", "afmhot", "autumn", "binary", "bone", "BrBG", "bwr", "cool", "coolwarm",
    "copper", "cubehelix", "Dark2", "flag", "gist_earth", "gist_gray", "gist_heat", "gist_ncar",
    "gist_rainbow", "gist_stern", "gist_yarg", "gnuplot", "gnuplot2", "gray", "Greens", "Greys",
    "hot", "hsv", "jet", "nipy_spectral", "ocean", "Oranges", "OrRd", "Paired",
    "Pastel1", "Pastel2", "pink", "PiYG", "PRGn", "PuBu", "PuBuGn", "PuOr", "PuRd", "Purples",
    "rainbow", "RdBu", "RdGy", "RdPu", "RdYlBu", "RdYlGn", "Reds", "seismic", "Set1", "Set2", "Set3",
    "spectral", "spring", "tab10", "tab20", "tab20b", "tab20c", "terrain", "turbo", "twilight",
    "twilight_shifted", "Wistia", "YlGn", "YlGnBu", "YlOrBr", "YlOrRd"
]
colormap = st.selectbox(
    'カラーマップを選択',
    colormaps_list,
    key="wc_colormap"
)

# フォントファイルのパス指定
# font_path = "./Streamlit/NotoSansJP-VariableFont_wght.ttf" # Noto Sans JP Thin
font_path = "./Streamlit/GenSekiGothic2JP-B.otf" # 源石ゴシックB


# フォントファイルの存在確認
if not os.path.exists(font_path):
    st.error(
        f"指定されたフォントが見つかりません。フォントパスを確認してください: {font_path}"
    )
else:
    # ワードクラウド生成ボタンがクリックされたとき
    if st.button("ワードクラウドを生成"):
        if user_input:
            if not selected_pos:
                st.error("少なくとも1つの品詞を選択してください。")
            else:
                try:
                    seed = st.session_state.get("wc_seed")
                    if seed is None:
                        seed = secrets.randbelow(2**31 - 1)
                    st.session_state["wc_seed"] = seed
                    wordcloud = generate_wordcloud(
                        user_input, 
                         width, 
                         height, 
                         background_color,
                         font_path, 
                         selected_pos, 
                         exclude_words, 
                         priority_nouns=priority_nouns,
                         max_words=max_words, 
                         collocations=collocations, 
                         min_font_size=min_font_size, 
                         colormap=colormap,
                         random_state=seed,
                    )

                    png_bytes = render_wordcloud_to_png_bytes(wordcloud)
                    st.session_state.last_png = png_bytes

                    # 保存用に「入力＋設定＋seed」を保持
                    st.session_state.last_config = {
                        "text": user_input,
                        "priority_nouns_input": priority_nouns_input,
                        "exclude_input": exclude_input,
                        "selected_pos": list(selected_pos),
                        "max_words": int(max_words),
                        "min_font_size": int(min_font_size),
                        "width": int(width),
                        "height": int(height),
                        "collocations": bool(collocations),
                        "background_color": background_color,
                        "colormap": colormap,
                        "seed": int(seed),
                    }

                    st.image(png_bytes)

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

    # ダウンロード＋保存ボタンを横並び(生成後のみ)
    if st.session_state.get("last_png") and st.session_state.get("last_config"):
        c1, c2 = st.columns([1, 1])

        with c1:
            st.download_button(
                label="画像をダウンロード",
                data=st.session_state.get("last_png"),
                file_name="wordcloud.png",
                mime="image/png",
            )

        with c2:
            if st.button("入力内容を保存"):
                try:
                    history = load_history()

                    item = {
                        "id": str(uuid.uuid4()),
                        "created_at": _now_iso_jst(),
                        "config": st.session_state.last_config,  # seed含む
                    }
                    history.append(item)
                    # 古い順に間引き
                    history = history[-MAX_HISTORY:]
                    save_history(history)

                    st.success("入力内容を保存しました（cookieに保存）")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存に失敗しました: {e}")


# =========================================================
# 下部UI：保存した設定
# =========================================================
st.divider()
st.caption("保存した設定（ブラウザcookieに保存）")

with st.expander("保存した設定", expanded=False):
    history = load_history()

    # リセット確認フロー
    if st.button("保存のリセット", type="secondary"):
        st.session_state.confirm_action = {"type": "reset"}
        st.rerun()

    if st.session_state.confirm_action and st.session_state.confirm_action.get("type") == "reset":
        st.warning("保存した設定をリセットしますか？")
        rc1, rc2 = st.columns([1, 1])
        with rc1:
            if st.button("リセットする", key="confirm_reset_yes"):
                reset_history()
                st.session_state.confirm_action = None
                st.success("保存をリセットしました")
                st.rerun()
        with rc2:
            if st.button("キャンセル", key="confirm_reset_no"):
                st.session_state.confirm_action = None
                st.rerun()

    if not history:
        st.caption("保存履歴はまだありません。")
    else:
        # 新しい順に表示
        for item in reversed(history):
            item_id = item.get("id")
            created_at = item.get("created_at", "")
            cfg = (item.get("config") or {})

            with st.container(border=True):
                top1, top2, top3 = st.columns([4, 1, 1])
                with top1:
                    st.caption(f"保存日時: {created_at}")

                with top2:
                    if st.button("読み込み", key=f"load_{item_id}"):
                        apply_config_to_inputs(cfg)
                        st.rerun()

                with top3:
                    if st.button("削除", key=f"delete_{item_id}"):
                        st.session_state.confirm_action = {"type": "delete", "id": item_id}
                        st.rerun()

                # 削除確認
                if (
                    st.session_state.confirm_action
                    and st.session_state.confirm_action.get("type") == "delete"
                    and st.session_state.confirm_action.get("id") == item_id
                ):
                    st.warning("この履歴を削除しますか？（元に戻せません）")
                    dc1, dc2 = st.columns([1, 1])
                    with dc1:
                        if st.button("削除する", key=f"confirm_delete_yes_{item_id}"):
                            try:
                                delete_history_item(item_id)
                                st.session_state.confirm_action = None
                                st.success("削除しました")
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除に失敗しました: {e}")
                    with dc2:
                        if st.button("キャンセル", key=f"confirm_delete_no_{item_id}"):
                            st.session_state.confirm_action = None
                            st.rerun()