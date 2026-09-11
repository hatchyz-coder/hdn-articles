# 世界の違和感 Publishing Contract

## 目的

「世界の違和感」を単発SNS投稿ではなく、HDNが所有する編集レーベルとして積み上げるための正本契約です。

正本は `https://article.hdnjapan.com/` に置きます。note、LinkedIn Newsletter、LinkedIn通常投稿、Facebook、Xは正本の代替ではなく、発見・固定読者化・再接触のための配信面です。

## 正本metadata

公開する日本語正本は次を必須とします。

```yaml
audiences:
  - general
section: world-frictions
series: world-frictions
cta: editorial
contentType: news-analysis
```

`contentType` は記事内容に応じて `opinion`、`case-study`、`practical-guide`、`regulation` へ変更できます。

## 編集構造

基本の思考順序は次です。

違和感 → 具体例 → なぜそう感じるか → 構造 → 一次資料・研究・信頼できる報道 → ハッチの考察 → 読者への問い

順序は記事ごとに最適化してよく、固定テンプレートとして機械的に並べません。ただし、事実、推測、意見を混同しません。

## 事実確認

一次資料が存在する主張は、可能な限り一次資料を確認します。二次報道だけで断定しません。

匿名投稿、SNS投稿、体験談は「事例」または「違和感の入口」として扱い、裏付けのない事実認定には使いません。

記事末尾には原則として `## 出典・一次情報・参考文献` を置き、読者が元情報へ辿れる状態にします。

## CTA

`cta: editorial` を使用します。一般読者へ不自然なクリニック相談CTAを出しません。

優先順位は次です。

1. 同じ「世界の違和感」の関連記事
2. 著者・HDNについて
3. 正本RSSまたは購読導線
4. LinkedIn Newsletter
5. note

## 配信bundle

1本の正本から、次の派生物を作ります。

```text
social/<slug>/
  note.md
  linkedin-newsletter.md
  linkedin.md
  facebook.md
  x.md
  reposts.md
```

同一全文の一斉コピーは禁止します。それぞれの媒体で入口、長さ、文脈、CTAを変えます。

## ハッチの作業

原則としてハッチが行うのは次の3点だけです。

1. 違和感・テーマを出す
2. 記事候補を選ぶ
3. 最終承認する

調査、一次資料確認、正本原稿、媒体別派生、画像案、再投稿切り口、検証は制作側でまとめて用意します。

## 公開Gate

公開前に次を満たします。

- 正本metadataが契約どおり
- 一次資料へ辿れる
- 事実と考察が区別されている
- 名誉毀損、医療広告、薬機法、景表法等のリスクを確認済み
- world-frictions記事にclinic営業CTAが混入していない
- 派生物が正本と同じ全文の単純複製になっていない
- 最終版にMarkdownのアスタリスク強調を使用していない
- 外部配信版からHDN正本へ戻る導線がある
