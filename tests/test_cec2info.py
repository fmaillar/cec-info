import unittest

from cec2info import body_to_texinfo, flatten_entries, parse_index


class ParseIndexTests(unittest.TestCase):
    def test_transparent_nested_list_wrapper(self) -> None:
        data = b"""
        <html><body><ul>
          <li><a href="__P1.HTM">Prologue</a><ul><ul>
            <li><a href="__P2.HTM">Section enfant</a></li>
          </ul></ul></li>
          <li><a href="__P3.HTM">Partie</a></li>
          <li>3</li><li>4</li><li>5</li><li>6</li><li>7</li><li>8</li>
          <li>9</li><li>10</li><li>11</li><li>12</li><li>13</li><li>14</li>
          <li>15</li><li>16</li><li>17</li><li>18</li><li>19</li><li>20</li>
        </ul></body></html>
        """
        roots = parse_index(data)
        entries = list(flatten_entries(roots))
        self.assertEqual(entries[1].title, "Section enfant")
        self.assertIs(entries[1].parent, entries[0])
        self.assertEqual(entries[1].depth, 2)


class TexinfoConversionTests(unittest.TestCase):
    def test_real_paragraph_is_indexed(self) -> None:
        result = body_to_texinfo("1 Dieu nous appelle.\n\n26 Nous croyons.")
        self.assertIn("@cindex 1", result)
        self.assertIn("@cindex 26", result)

    def test_split_biblical_reference_is_not_indexed(self) -> None:
        result = body_to_texinfo("128 Un texte (cf.\n\n1 P 3, 21).")
        self.assertIn("@cindex 128", result)
        self.assertNotIn("@cindex 1\n", result)
        self.assertIn("1 P 3, 21", result)


if __name__ == "__main__":
    unittest.main()
