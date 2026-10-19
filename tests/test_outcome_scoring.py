import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from outcome_scoring import assess, classify

IDEA = {'id': 'test', 'support_signals': ['output rises'], 'refute_signals': ['output falls']}

class Tests(unittest.TestCase):
    def test_no_news(self):
        self.assertEqual(assess([], IDEA)['score'], 50)
    def test_signals(self):
        e = [{'headline': 'Output rises in 2026'}, {'headline': 'Output falls in 2026'}]
        self.assertEqual(assess(e, IDEA)['score'], 50)
        self.assertEqual(classify(e[0], IDEA), 'support')
    def test_mixed(self):
        self.assertEqual(classify({'headline': 'Output rises then output falls'}, IDEA), 'mixed')
    def test_manual(self):
        self.assertEqual(assess([], dict(IDEA, reviewed_score=99))['score'], 99)

if __name__ == '__main__': unittest.main()
