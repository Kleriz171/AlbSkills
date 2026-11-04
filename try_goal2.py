"""Manual check for Goal 2:  python try_goal2.py"""

from loader import load_atlas

atlas = load_atlas('data/atlas.txt')
print(len(atlas.pipes), 'pipes,', len(atlas.areas), 'areas')

pipe = atlas.pipes['left-middle']
print('Pipe', pipe.name, '| size', pipe.size, '| comes from', pipe.comes_from)
print('  branches into:', [p.name for p in pipe.branches])
print('  feeds areas:  ', [a.name for a in pipe.areas])

pipe = atlas.pipes['left-middle-top']
print('Pipe', pipe.name, '| feeds areas:', [a.name for a in pipe.areas])

area = atlas.areas['memory']
print('Area', area.name, '| fed by', area.fed_by, '| symptoms', area.symptoms)
print('  does:', area.description)
