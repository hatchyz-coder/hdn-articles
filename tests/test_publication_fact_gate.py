import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gate', ROOT / 'scripts/publication_fact_gate.py')
gate = importlib.util.module_from_spec(spec)
sys.modules['gate'] = gate
spec.loader.exec_module(gate)


def article(body, published='2026-09-27'):
    return f'---\npublishedAt: {published}\n---\n\n{body}\n'


class FactGateTests(unittest.TestCase):
    def kinds(self, text):
        return {finding['kind'] for finding in gate.evaluate(text)['findings']}

    def test_unsupported_booking_rate_blocks(self):
        self.assertIn('unsupported_numeric_claim', self.kinds(article(
            '山形県の古民家宿では予約率18%向上、リピーター率30%増加。'
        )))

    def test_unsupported_sales_multiple_blocks(self):
        self.assertIn('unsupported_numeric_claim', self.kinds(article(
            '新潟県のシェアスペースでは平均売上1.2倍。'
        )))

    def test_unsourced_regional_case_blocks(self):
        self.assertIn('unsupported_case_claim', self.kinds(article(
            '福井県の民泊施設で導入後、利用率が改善。'
        )))

    def test_official_stat_with_inline_source_passes_numeric(self):
        text = article(
            '空き家率は13.8%です（https://www.stat.go.jp/data/jyutaku/index.html）。'
        )
        self.assertNotIn('unsupported_numeric_claim', self.kinds(text))

    def test_plain_date_does_not_trigger(self):
        self.assertTrue(gate.evaluate(article('2026年9月に運用を見直します。'))['publication_fact_gate'])

    def test_general_explanation_passes(self):
        self.assertTrue(gate.evaluate(article(
            '予約、決済、顧客対応を一つの導線として見直すことが重要です。'
        ))['publication_fact_gate'])

    def test_stale_line_pay_future_tense_blocks(self):
        self.assertIn('stale_future_tense', self.kinds(article(
            'LINE Pay終了に備え、PayPayなどへの移行計画が必要です。'
        )))

    def test_verified_product_feature_passes(self):
        text = article(
            'LINE公式アカウントではメッセージ配信ができます'
            '（https://www.linebiz.com/jp/service/line-official-account/）。'
        )
        self.assertNotIn('unverified_product_feature', self.kinds(text))

    def test_unverified_lhub_api_feature_blocks(self):
        self.assertIn('unverified_product_feature', self.kinds(article(
            'LHubからPayPay APIへ接続できます。'
        )))

    def test_opaque_browser_citation_is_not_evidence(self):
        self.assertIn('opaque_tool_citation', self.kinds(article(
            '空き家率は13.8%で過去最高です【0†L318-L336】。'
        )))

    def test_pr134_representative_text_is_blocked_for_multiple_reasons(self):
        text = article('''
空き家率は13.8％（約900万戸）で過去最高【0†L318-L336】。
LINE の継続課金（サブスク）機能を活用すれば、会員は毎回決済手続きを行う必要がありません。
LHubに決済APIを組み込み、PayPayへ接続できます。
山形県の古民家宿では予約率18%向上、リピーター率30%増加。
LINE Pay の終了を見越し、PayPayなど代替プラットフォームへ事前移行しましょう。
''')
        kinds = self.kinds(text)
        self.assertTrue({'unsupported_numeric_claim', 'opaque_tool_citation',
                         'unverified_product_feature', 'unsupported_case_claim',
                         'stale_future_tense'}.issubset(kinds))

    def test_english_stale_future_tense_blocks(self):
        self.assertIn('stale_future_tense', self.kinds(article(
            'Operators should prepare for the LINE Pay shutdown and migrate later.'
        )))


if __name__ == '__main__':
    unittest.main()
