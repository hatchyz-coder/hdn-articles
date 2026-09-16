from pathlib import Path
import tempfile
import unittest
import scripts.validate_world_frictions_bundle as validator

ARTICLE = '''---
title: "【テスト】世界の違和感"
description: "一次資料を確認しながら社会の違和感を構造として読み解くテスト用の記事説明です。読者が論点を理解できる長さを確保します。"
publishedAt: 2026-09-11
category: "世界の違和感"
tags: ["世界の違和感"]
author: "羽田野 剛士"
draft: true
cta: editorial
audiences: [general]
section: world-frictions
series: world-frictions
contentType: news-analysis
---
本文です。
## 出典・一次情報・参考文献
- Example Source: https://example.com/source
'''

class WorldFrictionsDistributionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); root=Path(self.tmp.name)
        self.article_dir=root/'src/content/articles'; self.en_dir=root/'src/content/articles-en'; self.social_dir=root/'social'
        self.article_dir.mkdir(parents=True); self.en_dir.mkdir(parents=True); self.social_dir.mkdir(parents=True)
        self.old=(validator.ARTICLE_DIR,validator.EN_ARTICLE_DIR,validator.SOCIAL_DIR)
        validator.ARTICLE_DIR=self.article_dir; validator.EN_ARTICLE_DIR=self.en_dir; validator.SOCIAL_DIR=self.social_dir
    def tearDown(self):
        validator.ARTICLE_DIR,validator.EN_ARTICLE_DIR,validator.SOCIAL_DIR=self.old; self.tmp.cleanup()
    def write_valid_bundle(self,slug='sample-friction',include_links=False):
        (self.article_dir/f'{slug}.md').write_text(ARTICLE,encoding='utf-8'); (self.en_dir/f'{slug}.md').write_text(ARTICLE,encoding='utf-8')
        social=self.social_dir/slug; social.mkdir(parents=True); canonical=validator.canonical_url(slug)
        facebook='【テスト】'+('本文です。' * 170)
        content={'note.md':'note向け編集版','linkedin-newsletter.md':'LinkedIn Newsletter向け編集版','linkedin.md':'【テスト】LinkedIn向け投稿','facebook.md':facebook,'x.md':'【テスト】X向け投稿','reposts.md':'- 数字から再投稿\n- 反対意見から再投稿\n- 構造の問いから再投稿'}
        for name,body in content.items():
            if include_links and name!='reposts.md': body+=f'\n\n記事はこちら\n{canonical}'
            (social/name).write_text(body+'\n',encoding='utf-8')
        return slug
    def test_valid_draft_bundle_passes(self): self.assertEqual(8,len(validator.validate_bundle(self.write_valid_bundle(),'draft')))
    def test_valid_final_bundle_requires_and_accepts_canonical_links(self): self.assertEqual(8,len(validator.validate_bundle(self.write_valid_bundle(include_links=True),'final')))
    def test_final_bundle_fails_without_canonical_links(self):
        with self.assertRaisesRegex(ValueError,'link back to canonical'): validator.validate_bundle(self.write_valid_bundle(),'final')
    def test_missing_en_pair_fails(self):
        slug=self.write_valid_bundle(); (self.en_dir/f'{slug}.md').unlink()
        with self.assertRaisesRegex(FileNotFoundError,'no EN pair'): validator.validate_bundle(slug,'draft')
    def test_wrong_cta_fails(self):
        slug=self.write_valid_bundle(); p=self.article_dir/f'{slug}.md'; p.write_text(p.read_text().replace('cta: editorial','cta: consultation'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'cta: editorial'): validator.validate_bundle(slug,'draft')
    def test_markdown_bold_in_derivative_fails(self):
        slug=self.write_valid_bundle(); (self.social_dir/slug/'facebook.md').write_text('【テスト】**強調は禁止**\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'asterisk emphasis'): validator.validate_bundle(slug,'draft')
    def test_short_facebook_final_fails(self):
        slug=self.write_valid_bundle(include_links=True); p=self.social_dir/slug/'facebook.md'; p.write_text('【短い】\n'+validator.canonical_url(slug),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Facebook copy must be'): validator.validate_bundle(slug,'final')

if __name__=='__main__': unittest.main()
