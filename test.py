from utils.text import name_match_score

print(name_match_score("CHINATU-NJOKU", "CHINATU NJOKU CHINYERE"))  # should be >=2
print(name_match_score("THOMPSON THOMPSON EZ", "THOMPSON EZEKIEL")) # should be >=2
