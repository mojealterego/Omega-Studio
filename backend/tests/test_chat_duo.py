import unittest
from omega_actions.ultimate.chat_duo import DuoSession, DuoError

class DuoTests(unittest.TestCase):
    def test_independent_review(self):
        calls=[]
        def author(prompt):
            calls.append(('author',prompt)); return 'def answer():\n    return 42\n'
        def reviewer(prompt):
            calls.append(('reviewer',prompt)); return 'APPROVE: reviewed'
        result=DuoSession(author,reviewer).run('Implement answer')
        self.assertTrue(result.approved)
        self.assertEqual([c[0] for c in calls],['author','reviewer'])
        self.assertIn('def answer()',calls[1][1])
    def test_rejection(self):
        result=DuoSession(lambda p:'code',lambda p:'REJECT: unsafe').run('task')
        self.assertFalse(result.approved)
        self.assertEqual(result.review,'REJECT: unsafe')
    def test_ambiguous_review_fails_closed(self):
        result=DuoSession(lambda p:'code',lambda p:'looks fine').run('task')
        self.assertFalse(result.approved)
    def test_empty_prompt(self):
        with self.assertRaises(DuoError):
            DuoSession(lambda p:'code',lambda p:'APPROVE: yes').run(' ')
    def test_empty_author_response(self):
        with self.assertRaises(DuoError):
            DuoSession(lambda p:'',lambda p:'APPROVE: yes').run('task')
    def test_oversized_output(self):
        with self.assertRaises(DuoError):
            DuoSession(lambda p:'x'*20,lambda p:'APPROVE: yes',max_chars=10).run('task')
    def test_no_automatic_execution(self):
        result=DuoSession(lambda p:'rm -rf /',lambda p:'APPROVE: reviewed').run('task')
        self.assertTrue(result.approved)
        self.assertFalse(result.executed)
