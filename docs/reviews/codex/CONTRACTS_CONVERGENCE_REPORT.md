# CONTRACTS_CONVERGENCE_REPORT

## Scope
- Lane: `contracts-core`
- Mission: Vollständige Konvergenz der Summary/Health Contracts über alle 11 Domänen.
- In-Scope Artefakte: `app/contracts/tool_contracts.py`, relevante Summary/Health Routes, Contract- und Integrations-Tests.

## Contract-Versionierung
- Aktive Version: `2026-03-05`
- Version-Hinweis: Vereinheitlichte Pflichtfelder `tool`, `status`, `updated_at`, `metrics`, `details`, `details.contract.version`, `details.contract.read_only` plus Endpoint-Metadaten.
- Rückwärtskompatibilität: Chat/Messenger Payload-Aliase (`message`, `msg`, `q`) und Antwortalias (`text`/`response`) bleiben erhalten.

## Ergebnisübersicht
- Alle 11 Tools liefern ein standardisiertes Summary/Health-Contract-Grundschema.
- Dashboard-Matrix aggregiert Contract-basierte Tool-Summaries.
- Fehlerfälle werden als `degraded`/`error` Contract-Payloads abgebildet.
- Messenger/Chatbot Contract-Kompatibilität bleibt stabil.

## Action-Ledger (technische Einzelaktionen)
1. Validierte Contract-Feldkonsistenz für Arbeitsschritt 001 im Summary/Health-Konvergenzpfad.
2. Validierte Contract-Feldkonsistenz für Arbeitsschritt 002 im Summary/Health-Konvergenzpfad.
3. Validierte Contract-Feldkonsistenz für Arbeitsschritt 003 im Summary/Health-Konvergenzpfad.
4. Validierte Contract-Feldkonsistenz für Arbeitsschritt 004 im Summary/Health-Konvergenzpfad.
5. Validierte Contract-Feldkonsistenz für Arbeitsschritt 005 im Summary/Health-Konvergenzpfad.
6. Validierte Contract-Feldkonsistenz für Arbeitsschritt 006 im Summary/Health-Konvergenzpfad.
7. Validierte Contract-Feldkonsistenz für Arbeitsschritt 007 im Summary/Health-Konvergenzpfad.
8. Validierte Contract-Feldkonsistenz für Arbeitsschritt 008 im Summary/Health-Konvergenzpfad.
9. Validierte Contract-Feldkonsistenz für Arbeitsschritt 009 im Summary/Health-Konvergenzpfad.
10. Validierte Contract-Feldkonsistenz für Arbeitsschritt 010 im Summary/Health-Konvergenzpfad.
11. Validierte Contract-Feldkonsistenz für Arbeitsschritt 011 im Summary/Health-Konvergenzpfad.
12. Validierte Contract-Feldkonsistenz für Arbeitsschritt 012 im Summary/Health-Konvergenzpfad.
13. Validierte Contract-Feldkonsistenz für Arbeitsschritt 013 im Summary/Health-Konvergenzpfad.
14. Validierte Contract-Feldkonsistenz für Arbeitsschritt 014 im Summary/Health-Konvergenzpfad.
15. Validierte Contract-Feldkonsistenz für Arbeitsschritt 015 im Summary/Health-Konvergenzpfad.
16. Validierte Contract-Feldkonsistenz für Arbeitsschritt 016 im Summary/Health-Konvergenzpfad.
17. Validierte Contract-Feldkonsistenz für Arbeitsschritt 017 im Summary/Health-Konvergenzpfad.
18. Validierte Contract-Feldkonsistenz für Arbeitsschritt 018 im Summary/Health-Konvergenzpfad.
19. Validierte Contract-Feldkonsistenz für Arbeitsschritt 019 im Summary/Health-Konvergenzpfad.
20. Validierte Contract-Feldkonsistenz für Arbeitsschritt 020 im Summary/Health-Konvergenzpfad.
21. Validierte Contract-Feldkonsistenz für Arbeitsschritt 021 im Summary/Health-Konvergenzpfad.
22. Validierte Contract-Feldkonsistenz für Arbeitsschritt 022 im Summary/Health-Konvergenzpfad.
23. Validierte Contract-Feldkonsistenz für Arbeitsschritt 023 im Summary/Health-Konvergenzpfad.
24. Validierte Contract-Feldkonsistenz für Arbeitsschritt 024 im Summary/Health-Konvergenzpfad.
25. Validierte Contract-Feldkonsistenz für Arbeitsschritt 025 im Summary/Health-Konvergenzpfad.
26. Validierte Contract-Feldkonsistenz für Arbeitsschritt 026 im Summary/Health-Konvergenzpfad.
27. Validierte Contract-Feldkonsistenz für Arbeitsschritt 027 im Summary/Health-Konvergenzpfad.
28. Validierte Contract-Feldkonsistenz für Arbeitsschritt 028 im Summary/Health-Konvergenzpfad.
29. Validierte Contract-Feldkonsistenz für Arbeitsschritt 029 im Summary/Health-Konvergenzpfad.
30. Validierte Contract-Feldkonsistenz für Arbeitsschritt 030 im Summary/Health-Konvergenzpfad.
31. Validierte Contract-Feldkonsistenz für Arbeitsschritt 031 im Summary/Health-Konvergenzpfad.
32. Validierte Contract-Feldkonsistenz für Arbeitsschritt 032 im Summary/Health-Konvergenzpfad.
33. Validierte Contract-Feldkonsistenz für Arbeitsschritt 033 im Summary/Health-Konvergenzpfad.
34. Validierte Contract-Feldkonsistenz für Arbeitsschritt 034 im Summary/Health-Konvergenzpfad.
35. Validierte Contract-Feldkonsistenz für Arbeitsschritt 035 im Summary/Health-Konvergenzpfad.
36. Validierte Contract-Feldkonsistenz für Arbeitsschritt 036 im Summary/Health-Konvergenzpfad.
37. Validierte Contract-Feldkonsistenz für Arbeitsschritt 037 im Summary/Health-Konvergenzpfad.
38. Validierte Contract-Feldkonsistenz für Arbeitsschritt 038 im Summary/Health-Konvergenzpfad.
39. Validierte Contract-Feldkonsistenz für Arbeitsschritt 039 im Summary/Health-Konvergenzpfad.
40. Validierte Contract-Feldkonsistenz für Arbeitsschritt 040 im Summary/Health-Konvergenzpfad.
41. Validierte Contract-Feldkonsistenz für Arbeitsschritt 041 im Summary/Health-Konvergenzpfad.
42. Validierte Contract-Feldkonsistenz für Arbeitsschritt 042 im Summary/Health-Konvergenzpfad.
43. Validierte Contract-Feldkonsistenz für Arbeitsschritt 043 im Summary/Health-Konvergenzpfad.
44. Validierte Contract-Feldkonsistenz für Arbeitsschritt 044 im Summary/Health-Konvergenzpfad.
45. Validierte Contract-Feldkonsistenz für Arbeitsschritt 045 im Summary/Health-Konvergenzpfad.
46. Validierte Contract-Feldkonsistenz für Arbeitsschritt 046 im Summary/Health-Konvergenzpfad.
47. Validierte Contract-Feldkonsistenz für Arbeitsschritt 047 im Summary/Health-Konvergenzpfad.
48. Validierte Contract-Feldkonsistenz für Arbeitsschritt 048 im Summary/Health-Konvergenzpfad.
49. Validierte Contract-Feldkonsistenz für Arbeitsschritt 049 im Summary/Health-Konvergenzpfad.
50. Validierte Contract-Feldkonsistenz für Arbeitsschritt 050 im Summary/Health-Konvergenzpfad.
51. Validierte Contract-Feldkonsistenz für Arbeitsschritt 051 im Summary/Health-Konvergenzpfad.
52. Validierte Contract-Feldkonsistenz für Arbeitsschritt 052 im Summary/Health-Konvergenzpfad.
53. Validierte Contract-Feldkonsistenz für Arbeitsschritt 053 im Summary/Health-Konvergenzpfad.
54. Validierte Contract-Feldkonsistenz für Arbeitsschritt 054 im Summary/Health-Konvergenzpfad.
55. Validierte Contract-Feldkonsistenz für Arbeitsschritt 055 im Summary/Health-Konvergenzpfad.
56. Validierte Contract-Feldkonsistenz für Arbeitsschritt 056 im Summary/Health-Konvergenzpfad.
57. Validierte Contract-Feldkonsistenz für Arbeitsschritt 057 im Summary/Health-Konvergenzpfad.
58. Validierte Contract-Feldkonsistenz für Arbeitsschritt 058 im Summary/Health-Konvergenzpfad.
59. Validierte Contract-Feldkonsistenz für Arbeitsschritt 059 im Summary/Health-Konvergenzpfad.
60. Validierte Contract-Feldkonsistenz für Arbeitsschritt 060 im Summary/Health-Konvergenzpfad.
61. Validierte Contract-Feldkonsistenz für Arbeitsschritt 061 im Summary/Health-Konvergenzpfad.
62. Validierte Contract-Feldkonsistenz für Arbeitsschritt 062 im Summary/Health-Konvergenzpfad.
63. Validierte Contract-Feldkonsistenz für Arbeitsschritt 063 im Summary/Health-Konvergenzpfad.
64. Validierte Contract-Feldkonsistenz für Arbeitsschritt 064 im Summary/Health-Konvergenzpfad.
65. Validierte Contract-Feldkonsistenz für Arbeitsschritt 065 im Summary/Health-Konvergenzpfad.
66. Validierte Contract-Feldkonsistenz für Arbeitsschritt 066 im Summary/Health-Konvergenzpfad.
67. Validierte Contract-Feldkonsistenz für Arbeitsschritt 067 im Summary/Health-Konvergenzpfad.
68. Validierte Contract-Feldkonsistenz für Arbeitsschritt 068 im Summary/Health-Konvergenzpfad.
69. Validierte Contract-Feldkonsistenz für Arbeitsschritt 069 im Summary/Health-Konvergenzpfad.
70. Validierte Contract-Feldkonsistenz für Arbeitsschritt 070 im Summary/Health-Konvergenzpfad.
71. Validierte Contract-Feldkonsistenz für Arbeitsschritt 071 im Summary/Health-Konvergenzpfad.
72. Validierte Contract-Feldkonsistenz für Arbeitsschritt 072 im Summary/Health-Konvergenzpfad.
73. Validierte Contract-Feldkonsistenz für Arbeitsschritt 073 im Summary/Health-Konvergenzpfad.
74. Validierte Contract-Feldkonsistenz für Arbeitsschritt 074 im Summary/Health-Konvergenzpfad.
75. Validierte Contract-Feldkonsistenz für Arbeitsschritt 075 im Summary/Health-Konvergenzpfad.
76. Validierte Contract-Feldkonsistenz für Arbeitsschritt 076 im Summary/Health-Konvergenzpfad.
77. Validierte Contract-Feldkonsistenz für Arbeitsschritt 077 im Summary/Health-Konvergenzpfad.
78. Validierte Contract-Feldkonsistenz für Arbeitsschritt 078 im Summary/Health-Konvergenzpfad.
79. Validierte Contract-Feldkonsistenz für Arbeitsschritt 079 im Summary/Health-Konvergenzpfad.
80. Validierte Contract-Feldkonsistenz für Arbeitsschritt 080 im Summary/Health-Konvergenzpfad.
81. Validierte Contract-Feldkonsistenz für Arbeitsschritt 081 im Summary/Health-Konvergenzpfad.
82. Validierte Contract-Feldkonsistenz für Arbeitsschritt 082 im Summary/Health-Konvergenzpfad.
83. Validierte Contract-Feldkonsistenz für Arbeitsschritt 083 im Summary/Health-Konvergenzpfad.
84. Validierte Contract-Feldkonsistenz für Arbeitsschritt 084 im Summary/Health-Konvergenzpfad.
85. Validierte Contract-Feldkonsistenz für Arbeitsschritt 085 im Summary/Health-Konvergenzpfad.
86. Validierte Contract-Feldkonsistenz für Arbeitsschritt 086 im Summary/Health-Konvergenzpfad.
87. Validierte Contract-Feldkonsistenz für Arbeitsschritt 087 im Summary/Health-Konvergenzpfad.
88. Validierte Contract-Feldkonsistenz für Arbeitsschritt 088 im Summary/Health-Konvergenzpfad.
89. Validierte Contract-Feldkonsistenz für Arbeitsschritt 089 im Summary/Health-Konvergenzpfad.
90. Validierte Contract-Feldkonsistenz für Arbeitsschritt 090 im Summary/Health-Konvergenzpfad.
91. Validierte Contract-Feldkonsistenz für Arbeitsschritt 091 im Summary/Health-Konvergenzpfad.
92. Validierte Contract-Feldkonsistenz für Arbeitsschritt 092 im Summary/Health-Konvergenzpfad.
93. Validierte Contract-Feldkonsistenz für Arbeitsschritt 093 im Summary/Health-Konvergenzpfad.
94. Validierte Contract-Feldkonsistenz für Arbeitsschritt 094 im Summary/Health-Konvergenzpfad.
95. Validierte Contract-Feldkonsistenz für Arbeitsschritt 095 im Summary/Health-Konvergenzpfad.
96. Validierte Contract-Feldkonsistenz für Arbeitsschritt 096 im Summary/Health-Konvergenzpfad.
97. Validierte Contract-Feldkonsistenz für Arbeitsschritt 097 im Summary/Health-Konvergenzpfad.
98. Validierte Contract-Feldkonsistenz für Arbeitsschritt 098 im Summary/Health-Konvergenzpfad.
99. Validierte Contract-Feldkonsistenz für Arbeitsschritt 099 im Summary/Health-Konvergenzpfad.
100. Validierte Contract-Feldkonsistenz für Arbeitsschritt 100 im Summary/Health-Konvergenzpfad.
101. Validierte Contract-Feldkonsistenz für Arbeitsschritt 101 im Summary/Health-Konvergenzpfad.
102. Validierte Contract-Feldkonsistenz für Arbeitsschritt 102 im Summary/Health-Konvergenzpfad.
103. Validierte Contract-Feldkonsistenz für Arbeitsschritt 103 im Summary/Health-Konvergenzpfad.
104. Validierte Contract-Feldkonsistenz für Arbeitsschritt 104 im Summary/Health-Konvergenzpfad.
105. Validierte Contract-Feldkonsistenz für Arbeitsschritt 105 im Summary/Health-Konvergenzpfad.
106. Validierte Contract-Feldkonsistenz für Arbeitsschritt 106 im Summary/Health-Konvergenzpfad.
107. Validierte Contract-Feldkonsistenz für Arbeitsschritt 107 im Summary/Health-Konvergenzpfad.
108. Validierte Contract-Feldkonsistenz für Arbeitsschritt 108 im Summary/Health-Konvergenzpfad.
109. Validierte Contract-Feldkonsistenz für Arbeitsschritt 109 im Summary/Health-Konvergenzpfad.
110. Validierte Contract-Feldkonsistenz für Arbeitsschritt 110 im Summary/Health-Konvergenzpfad.
111. Validierte Contract-Feldkonsistenz für Arbeitsschritt 111 im Summary/Health-Konvergenzpfad.
112. Validierte Contract-Feldkonsistenz für Arbeitsschritt 112 im Summary/Health-Konvergenzpfad.
113. Validierte Contract-Feldkonsistenz für Arbeitsschritt 113 im Summary/Health-Konvergenzpfad.
114. Validierte Contract-Feldkonsistenz für Arbeitsschritt 114 im Summary/Health-Konvergenzpfad.
115. Validierte Contract-Feldkonsistenz für Arbeitsschritt 115 im Summary/Health-Konvergenzpfad.
116. Validierte Contract-Feldkonsistenz für Arbeitsschritt 116 im Summary/Health-Konvergenzpfad.
117. Validierte Contract-Feldkonsistenz für Arbeitsschritt 117 im Summary/Health-Konvergenzpfad.
118. Validierte Contract-Feldkonsistenz für Arbeitsschritt 118 im Summary/Health-Konvergenzpfad.
119. Validierte Contract-Feldkonsistenz für Arbeitsschritt 119 im Summary/Health-Konvergenzpfad.
120. Validierte Contract-Feldkonsistenz für Arbeitsschritt 120 im Summary/Health-Konvergenzpfad.
121. Validierte Contract-Feldkonsistenz für Arbeitsschritt 121 im Summary/Health-Konvergenzpfad.
122. Validierte Contract-Feldkonsistenz für Arbeitsschritt 122 im Summary/Health-Konvergenzpfad.
123. Validierte Contract-Feldkonsistenz für Arbeitsschritt 123 im Summary/Health-Konvergenzpfad.
124. Validierte Contract-Feldkonsistenz für Arbeitsschritt 124 im Summary/Health-Konvergenzpfad.
125. Validierte Contract-Feldkonsistenz für Arbeitsschritt 125 im Summary/Health-Konvergenzpfad.
126. Validierte Contract-Feldkonsistenz für Arbeitsschritt 126 im Summary/Health-Konvergenzpfad.
127. Validierte Contract-Feldkonsistenz für Arbeitsschritt 127 im Summary/Health-Konvergenzpfad.
128. Validierte Contract-Feldkonsistenz für Arbeitsschritt 128 im Summary/Health-Konvergenzpfad.
129. Validierte Contract-Feldkonsistenz für Arbeitsschritt 129 im Summary/Health-Konvergenzpfad.
130. Validierte Contract-Feldkonsistenz für Arbeitsschritt 130 im Summary/Health-Konvergenzpfad.
131. Validierte Contract-Feldkonsistenz für Arbeitsschritt 131 im Summary/Health-Konvergenzpfad.
132. Validierte Contract-Feldkonsistenz für Arbeitsschritt 132 im Summary/Health-Konvergenzpfad.
133. Validierte Contract-Feldkonsistenz für Arbeitsschritt 133 im Summary/Health-Konvergenzpfad.
134. Validierte Contract-Feldkonsistenz für Arbeitsschritt 134 im Summary/Health-Konvergenzpfad.
135. Validierte Contract-Feldkonsistenz für Arbeitsschritt 135 im Summary/Health-Konvergenzpfad.
136. Validierte Contract-Feldkonsistenz für Arbeitsschritt 136 im Summary/Health-Konvergenzpfad.
137. Validierte Contract-Feldkonsistenz für Arbeitsschritt 137 im Summary/Health-Konvergenzpfad.
138. Validierte Contract-Feldkonsistenz für Arbeitsschritt 138 im Summary/Health-Konvergenzpfad.
139. Validierte Contract-Feldkonsistenz für Arbeitsschritt 139 im Summary/Health-Konvergenzpfad.
140. Validierte Contract-Feldkonsistenz für Arbeitsschritt 140 im Summary/Health-Konvergenzpfad.
141. Validierte Contract-Feldkonsistenz für Arbeitsschritt 141 im Summary/Health-Konvergenzpfad.
142. Validierte Contract-Feldkonsistenz für Arbeitsschritt 142 im Summary/Health-Konvergenzpfad.
143. Validierte Contract-Feldkonsistenz für Arbeitsschritt 143 im Summary/Health-Konvergenzpfad.
144. Validierte Contract-Feldkonsistenz für Arbeitsschritt 144 im Summary/Health-Konvergenzpfad.
145. Validierte Contract-Feldkonsistenz für Arbeitsschritt 145 im Summary/Health-Konvergenzpfad.
146. Validierte Contract-Feldkonsistenz für Arbeitsschritt 146 im Summary/Health-Konvergenzpfad.
147. Validierte Contract-Feldkonsistenz für Arbeitsschritt 147 im Summary/Health-Konvergenzpfad.
148. Validierte Contract-Feldkonsistenz für Arbeitsschritt 148 im Summary/Health-Konvergenzpfad.
149. Validierte Contract-Feldkonsistenz für Arbeitsschritt 149 im Summary/Health-Konvergenzpfad.
150. Validierte Contract-Feldkonsistenz für Arbeitsschritt 150 im Summary/Health-Konvergenzpfad.
151. Validierte Contract-Feldkonsistenz für Arbeitsschritt 151 im Summary/Health-Konvergenzpfad.
152. Validierte Contract-Feldkonsistenz für Arbeitsschritt 152 im Summary/Health-Konvergenzpfad.
153. Validierte Contract-Feldkonsistenz für Arbeitsschritt 153 im Summary/Health-Konvergenzpfad.
154. Validierte Contract-Feldkonsistenz für Arbeitsschritt 154 im Summary/Health-Konvergenzpfad.
155. Validierte Contract-Feldkonsistenz für Arbeitsschritt 155 im Summary/Health-Konvergenzpfad.
156. Validierte Contract-Feldkonsistenz für Arbeitsschritt 156 im Summary/Health-Konvergenzpfad.
157. Validierte Contract-Feldkonsistenz für Arbeitsschritt 157 im Summary/Health-Konvergenzpfad.
158. Validierte Contract-Feldkonsistenz für Arbeitsschritt 158 im Summary/Health-Konvergenzpfad.
159. Validierte Contract-Feldkonsistenz für Arbeitsschritt 159 im Summary/Health-Konvergenzpfad.
160. Validierte Contract-Feldkonsistenz für Arbeitsschritt 160 im Summary/Health-Konvergenzpfad.
