import os  # フォントファイルの存在確認に使用
import streamlit as st  # Webアプリフレームワーク
from janome.tokenizer import Tokenizer  # 日本語テキストの形態素解析
from wordcloud import WordCloud  # ワードクラウド生成
import matplotlib.pyplot as plt  # ワードクラウドの描画

def tokenize_japanese(text, selected_pos, exclude_words=None):
    """
    日本語テキストを形態素解析し、選択した品詞のみを含む単語の文字列を返す。

    Args:
        text (str): 解析対象の日本語テキスト。
        selected_pos (list): 含める品詞のリスト。
        exclude_words (list, optional): 除外する単語のリスト。

    Returns:
        str: スペースで区切られた単語の文字列。
    """
    tokenizer = Tokenizer()
    tokens = tokenizer.tokenize(text)
    if exclude_words is None:
        exclude_words = []
    words = ' '.join([
        token.base_form
        for token in tokens
        if token.part_of_speech.split(',')[0] in selected_pos
        and token.base_form not in exclude_words
    ])
    return words

def generate_wordcloud(text, width, height, background_color, font_path, selected_pos, exclude_words=None):
    """
    トークン化された日本語テキストからワードクラウドを生成する。

    Args:
        text (str): ワードクラウド生成元の日本語テキスト。
        width (int): ワードクラウド画像の幅。
        height (int): ワードクラウド画像の高さ。
        background_color (str): ワードクラウドの背景色。
        font_path (str): フォントファイルへのパス。
        selected_pos (list): 含める品詞のリスト。
        exclude_words (list, optional): 除外する単語のリスト。

    Returns:
        WordCloud: 生成されたWordCloudオブジェクト。
    """
    words = tokenize_japanese(text, selected_pos, exclude_words)
    wordcloud = WordCloud(
        font_path=font_path,
        width=width,
        height=height,
        background_color=background_color
    ).generate(words)
    return wordcloud

# =================================================================

# Streamlitアプリのタイトル
st.title("ワードクラウドジェネレーター")

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

# ワードクラウド画像の幅入力
width = st.number_input(
    "ワードクラウドの幅（ピクセル）",
    min_value=100,
    max_value=4000,
    value=1920,
    step=1
)

# ワードクラウド画像の高さ入力
height = st.number_input(
    "ワードクラウドの高さ（ピクセル）",
    min_value=100,
    max_value=4000,
    value=1080,
    step=1
)

# 背景色の選択
background_color = st.color_picker("背景色を選択してください", "#f4f5f7")

# フォントファイルのパス指定
font_path = "./Streamlit/NotoSansJP-VariableFont_wght.ttf"  # フォントファイルが同じディレクトリにあることを確認

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
                        font_path, selected_pos, exclude_words
                    )

                    # ワードクラウドの描画
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis("off")

                    # Streamlit上にワードクラウドを表示
                    st.pyplot(fig)
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
        else:
            st.error("ワードクラウドを生成するテキストを入力してください。")
