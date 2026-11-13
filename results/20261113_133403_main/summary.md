# 20261113_133403_main

## Execution accuracy by arm (%)

| arm        |   answers |   EX corrected key |   EX original key |   strict, corrected |   no answer |   answered on last call |   cost per answer ($) |   total cost ($) |
|:-----------|----------:|-------------------:|------------------:|--------------------:|------------:|------------------------:|----------------------:|-----------------:|
| schema     |       496 |               61.9 |              60.1 |                61.5 |          10 |                      63 |               0.00151 |            0.749 |
| dictionary |       496 |               69.4 |              67.1 |                69   |           6 |                      37 |               0.00127 |            0.63  |
| context    |       496 |               65.1 |              62.1 |                64.9 |          11 |                      36 |               0.0014  |            0.692 |

## Leads on the corrected key, 496 questions (points)

|                      |   lead |   95% low |   95% high |   questions won |   questions lost |
|:---------------------|-------:|----------:|-----------:|----------------:|-----------------:|
| context - schema     |    3.2 |      -0.4 |        7.1 |              53 |               37 |
| context - dictionary |   -4.2 |      -7.5 |       -1   |              26 |               47 |
| dictionary - schema  |    7.5 |       4   |       11.1 |              60 |               23 |

## By database, corrected key (%)

| db                      |   questions |   schema |   dictionary |   context |   context - schema |   95% low |   95% high |
|:------------------------|------------:|---------:|-------------:|----------:|-------------------:|----------:|-----------:|
| california_schools      |          30 |     40   |         40   |      46.7 |                6.7 |      -6.7 |       20   |
| card_games              |          51 |     64.7 |         68.6 |      62.7 |               -2   |     -11.8 |        7.8 |
| codebase_community      |          48 |     56.2 |         75   |      70.8 |               14.6 |       6.2 |       25   |
| debit_card_specializing |          30 |     63.3 |         70   |      70   |                6.7 |       0   |       16.7 |
| european_football_2     |          51 |     68.6 |         78.4 |      74.5 |                5.9 |      -3.9 |       15.7 |
| financial               |          30 |     50   |         66.7 |      60   |               10   |      -6.7 |       26.7 |
| formula_1               |          66 |     57.6 |         53   |      51.5 |               -6.1 |     -15.2 |        3   |
| student_club            |          48 |     79.2 |         77.1 |      72.9 |               -6.2 |     -18.8 |        4.2 |
| superhero               |          52 |     76.9 |         82.7 |      78.8 |                1.9 |      -7.7 |       11.5 |
| thrombosis_prediction   |          50 |     36   |         60   |      50   |               14   |      -4   |       32   |
| toxicology              |          40 |     80   |         87.5 |      77.5 |               -2.5 |     -17.5 |       12.5 |
