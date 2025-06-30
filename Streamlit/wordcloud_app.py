import os
import io
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

def tokenize_japanese(text, selected_pos, exclude_words=None):
    tokenizer = Tokenizer()
    tokens = tokenizer.tokenize(text)
    if exclude_words is None:
        exclude_words = []
    words = ' '.join([
        token.base_form
        for token in tokens
        if token.part_of_speech.split(',')[0] in selected_pos
        and token.base_form not in exclude_words
        and len(token.base_form) > 1
    ])
    return words

def generate_wordcloud(text, width, height, background_color, font_path, selected_pos, exclude_words=None, max_words=50, collocations=False, min_font_size=10):
    horizontal = 0.5
    if collocations:
        horizontal = 1.0
    words = tokenize_japanese(text, selected_pos, exclude_words)
    wordcloud = WordCloud(
        font_path=font_path,
        width=width,
        height=height,
        background_color=background_color,
        max_words=max_words,
        min_font_size=min_font_size,
        collocations=collocations,
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
max_words = st.slider(
    "表示する最大単語数",
    min_value=5,
    max_value=200,
    value=50,
    step=1
)

# 横書きのみ
collocations = st.checkbox(
    "横書きのみ",
    value=True
)

# 最小フォントサイズ
min_font_size = st.slider(
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
    value=1920,
    step=1
)

# ワードクラウド画像の高さ入力
height = st.number_input(
    "ワードクラウドの高さ",
    min_value=100,
    max_value=4000,
    value=1080,
    step=1
)

# 背景色の選択
background_color = st.color_picker("背景色を選択してください", "#f4f5f7")

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
                        user_input, width, height, background_color,
                        font_path, selected_pos, exclude_words, max_words, collocations, min_font_size
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
