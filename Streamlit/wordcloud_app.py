import os
import io
import re
import streamlit as st
from janome.tokenizer import Tokenizer
from wordcloud import WordCloud
import matplotlib.pyplot as plt

#ページコンフィグ
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

def apply_priority_nouns(text, priority_nouns):
    """
    priority_nouns に指定された語を最優先で1語として扱うため、
    文字列中の該当箇所をプレースホルダに置換してからJanomeに渡す。
    """

    if not priority_nouns:
        return text, {}

    # 重複除去 + 長い語を先に（部分一致の事故を減らす）
    uniq = sorted(set([w for w in priority_nouns if w]), key=len, reverse=True)
    if not uniq:
        return text, {}

    word_to_ph = {}
    ph_to_word = {}
    for i, w in enumerate(uniq):
        ph = f"__PRIORITY_NOUN_{i}__"
        word_to_ph[w] = ph
        ph_to_word[ph] = w

    pattern = re.compile("|".join(map(re.escape, uniq)))

    def repl(m):
        w = m.group(0)
        ph = word_to_ph[w]
        # 前後に空白を入れてトークンとして分離しやすくする
        return f" {ph} "

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
    colormap=None
):
    horizontal = 0.5
    if collocations:
        horizontal = 1.0

    words = tokenize_japanese(text, selected_pos, exclude_words, priority_nouns)

    wordcloud = WordCloud(
        font_path=font_path,
        width=width,
        height=height,
        background_color=background_color,
        max_words=max_words,
        min_font_size=min_font_size,
        collocations=collocations,
        colormap=colormap,
        prefer_horizontal=horizontal
    ).generate(words)

    return wordcloud

# =================================================================

# Streamlitアプリのタイトル
st.title("ワードクラウドジェネレーター☁️")

# ユーザーからのテキスト入力
user_input = st.text_area(
    "テキストを入力してください"
)

# 名詞リスト
priority_nouns_input = st.text_input(
    "名詞として優先したい単語を入力してください（カンマ区切り）",
    value=""
)
priority_nouns = [w.strip() for w in priority_nouns_input.split(',') if w.strip()]

# 除外する単語の入力
exclude_input = st.text_input(
    "除外する単語を入力してください（カンマ区切り）",
    value="的, こと, もの, それ, これ, ため, よう, そこ, どこ, とき, あと, みたい, ような"
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
    default=['名詞']  # デフォルト選択
)

# 表示する単語数の上限
max_words = st.number_input(
    "表示する最大単語数",
    min_value=5,
    max_value=200,
    value=50,
    step=1
)

# 最小フォントサイズ
min_font_size = st.number_input(
    "最小フォントサイズ",
    min_value=1,
    max_value=100,
    value=10,
    step=1
)

# ワードクラウド画像の幅入力
width = st.number_input(
    "ワードクラウドの幅",
    min_value=100,
    max_value=4000,
    value=800,
    step=1
)

# ワードクラウド画像の高さ入力
height = st.number_input(
    "ワードクラウドの高さ",
    min_value=100,
    max_value=4000,
    value=600,
    step=1
)

# 横書きのみ
collocations = st.checkbox(
    "横書きのみ",
    value=True
)

# 背景色の選択
background_color = st.color_picker("背景色を選択", "#f4f5f7")

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
colormap = st.selectbox('カラーマップを選択', colormaps_list)

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
                         colormap=colormap
                    )

                    # ワードクラウドの描画
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis("off")

                    # Streamlit上にワードクラウドを表示
                    st.pyplot(fig)
                    # ワードクラウド画像をバイナリに変換してダウンロード用に保存
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches='tight')
                    buf.seek(0)
                    
                    # ダウンロードボタンを表示
                    st.download_button(
                        label="画像をダウンロード",
                        data=buf,
                        file_name="wordcloud.png",
                        mime="image/png"
                    )
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
        else:
            st.error("ワードクラウドを生成するテキストを入力してください。")
