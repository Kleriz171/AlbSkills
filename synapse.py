"""Synapse: the program you start. Commands: atlas load / pipes / areas / show / find."""

import commands
from loader import AtlasError, load_atlas
import roadmap
import routing
import triage
from symptoms import SymptomError, load_symptoms

DEFAULT_ATLAS = 'data/atlas.txt'
DEFAULT_SYMPTOMS = 'data/symptoms.txt'
DEFAULT_CASES = 'data/cases.json'
DEFAULT_ROADS = 'data/roads.txt'
DEFAULT_HOSPITALS = 'data/hospitals.txt'
UNIT_USAGE = 'Usage: unit run <file>'
ROUTE_USAGE = 'Usage: route from <city> | <case id> | whatif <city> <ability>'
MAP_USAGE = 'Usage: map load <path> | roads | hospitals | coverage'
TRIAGE_USAGE = 'Usage: triage load <path> | symptoms | new | list | show <id> | update <id> | urgent'
LESION_USAGE = 'Usage: lesion block <pipe>[, <pipe>...] | risk <area> | tree <pipe>'
ATLAS_USAGE ='Usage: atlas load <path> | pipes | areas | show <name> | find <word> | tree | path <area>'


def load_command(state, path):
    """Try to load an atlas. If anything is wrong, keep the old one (all or nothing)."""
    try:
        atlas = load_atlas(path)
    except AtlasError as error:
        for message in error.messages:            # report EVERY problem, one per line
            print(f'ERROR: {message}')
        if state['path']:
            print(f'Atlas not loaded. Still using {state["path"]}.')
        else:
            print('Atlas not loaded.')
        return

    state['atlas'] = atlas                    # only now do we replace the old atlas
    state['path'] = path
    summary = f'{len(atlas.pipes)} pipes, {len(atlas.areas)} areas'
    if atlas.bridges:                         # only mention bridges when there are some
        summary += f', {len(atlas.bridges)} bridges'
    print(f'SUCCESS: Atlas loaded from {path}: {summary}.')


def atlas_command(state, args):
    """Handle everything after the word 'atlas'."""
    if not args:
        raise ValueError(f'Missing subcommand. {ATLAS_USAGE}')
    sub, rest = args[0], args[1:]

    if sub == 'load':
        if not rest:
            raise ValueError('Missing path. Usage: atlas load <path>')
        load_command(state, ' '.join(rest))
        return

    if sub not in ('pipes', 'areas', 'show', 'find', 'tree', 'path'):
        raise ValueError(f'Unknown atlas command "{sub}". {ATLAS_USAGE}')
    atlas = state['atlas']
    if atlas is None:
        raise ValueError('No atlas is loaded. Use: atlas load <path>')

    if sub == 'pipes':
        commands.show_pipes(atlas)
    elif sub == 'areas':
        commands.show_areas(atlas)
    elif sub == 'tree':
        commands.show_tree(atlas)
    elif sub == 'path':
        if not rest:
            raise ValueError('Missing area. Usage: atlas path <area>')
        commands.show_paths(atlas, ' '.join(rest))
    elif sub == 'show':
        if not rest:
            raise ValueError('Missing name. Usage: atlas show <name>')
        commands.show_one(atlas, ' '.join(rest))
    elif sub == 'find':
        if not rest:
            raise ValueError('Missing word. Usage: atlas find <word>')
        commands.find(atlas, ' '.join(rest))


def load_symptoms_command(state, path):
    """Try to load a symptom list. If anything is wrong, keep the old one (all or nothing)."""
    try:
        symptoms = load_symptoms(path)
    except SymptomError as error:
        for message in error.messages:
            print(f'ERROR: {message}')
        if state['symptoms_path']:
            print(f'Symptoms not loaded. Still using {state["symptoms_path"]}.')
        else:
            print('Symptoms not loaded.')
        return

    state['symptoms'] = symptoms
    state['symptoms_path'] = path
    print(f'SUCCESS: Symptoms loaded from {path}: {len(symptoms)} symptoms.')


def load_map_command(state, path):
    """Load a roads file OR a hospitals file (the first record says which). All or nothing:
    if anything is wrong, every problem is reported and the old data is kept."""
    kind = None
    try:
        records = roadmap.read_records(path)
        kind = roadmap.kind_of_file(records, path)
        if kind == 'roads':
            roads = roadmap.build_roads(records, path, state['hospitals'], state['hospitals_path'])
        else:
            if state['roads'] is None:
                raise roadmap.MapError(['No roads are loaded yet. Load a roads file first.'])
            hospitals = roadmap.build_hospitals(records, path, state['roads'])
    except roadmap.MapError as error:
        for message in error.messages:
            print(f'ERROR: {message}')
        old = state.get(f'{kind}_path') if kind else None
        print(f'{kind.capitalize() if kind else "Map file"} not loaded.'
              + (f' Still using {old}.' if old else ''))
        return

    if kind == 'roads':
        state['roads'], state['roads_path'] = roads, path
        print(f'SUCCESS: Roads loaded from {path}: {len(roads.cities)} cities, '
              f'{roads.road_count()} roads.')
    else:
        state['hospitals'], state['hospitals_path'] = hospitals, path
        print(f'SUCCESS: Hospitals loaded from {path}: {len(hospitals)} hospitals.')


def map_command(state, args):
    """Handle everything after the word 'map'."""
    if not args:
        raise ValueError(f'Missing subcommand. {MAP_USAGE}')
    sub, rest = args[0], args[1:]
    if sub == 'load':
        if not rest:
            raise ValueError('Missing path. Usage: map load <path>')
        load_map_command(state, ' '.join(rest))
        return
    if sub not in ('roads', 'hospitals', 'coverage'):
        raise ValueError(f'Unknown map command "{sub}". {MAP_USAGE}')
    if state['roads'] is None:
        raise ValueError('No roads are loaded. Use: map load <path>')
    if sub == 'roads':
        commands.show_roads(state['roads'])
    elif sub == 'coverage':
        if not state['hospitals']:
            raise ValueError('No hospitals are loaded. Use: map load <path>')
        commands.show_coverage(routing.coverage(state['roads'], state['hospitals']),
                               routing.FAR_LIMIT)
    else:
        commands.show_hospitals(state['hospitals'])


def route_command(state, args):
    """Handle everything after the word 'route'."""
    if not args:
        raise ValueError(f'Missing subcommand. {ROUTE_USAGE}')
    sub, rest = args[0], args[1:]
    roads, hospitals = state['roads'], state['hospitals']
    if roads is None:
        raise ValueError('No roads are loaded. Use: map load <path>')
    if not hospitals:
        raise ValueError('No hospitals are loaded. Use: map load <path>')

    if sub == 'whatif':
        if len(rest) < 2:
            raise ValueError('Missing city or ability. Usage: route whatif <city> <ability>')
        triage.route_whatif(state, ' '.join(rest[:-1]), rest[-1])    # the last word is the ability
        return
    if sub != 'from':                          # anything else is a case id: route P-0001
        if not state['cases_ok']:
            raise ValueError(f'{state["cases_path"]} could not be read, so no case can be saved.')
        triage.route_case(state, ' '.join(args))
        return
    if not rest:
        raise ValueError('Missing city. Usage: route from <city>')

    typed = ' '.join(rest)
    city = routing.find_city(roads, typed)
    if city is None:
        raise ValueError(f'The city "{typed}" is not on the map.')
    routes = routing.hospital_routes(roads, hospitals, city)
    if not routes:
        raise ValueError(f'No road leads from {city} to any hospital.')
    commands.show_routes(city, routes, len(hospitals) - len(routes))


def unit_command(state, args):
    """Handle everything after the word 'unit'."""
    if not args:
        raise ValueError(f'Missing subcommand. {UNIT_USAGE}')
    sub, rest = args[0], args[1:]
    if sub != 'run':
        raise ValueError(f'Unknown unit command "{sub}". {UNIT_USAGE}')
    if not rest:
        raise ValueError('Missing file. Usage: unit run <file>')
    if not state['cases_ok']:
        raise ValueError(f'{state["cases_path"]} could not be read, so the cases cannot be used.')
    triage.run_unit(state, ' '.join(rest))


def load_cases_command(state):
    """Read the saved cases when the program starts. If the file is damaged we say so and
    refuse to create new cases, so we can never overwrite it with an empty list."""
    try:
        cases = triage.load_cases(state['cases_path'])
    except triage.CaseFileError as error:
        state['cases_ok'] = False
        print(f'ERROR: {error}')
        print('New cases are disabled so the file is not overwritten. Fix or move it, then restart.')
        return
    state['cases'] = cases
    state['next_case_number'] = triage.next_number(cases)
    if cases:
        print(f'Loaded {len(cases)} saved cases from {state["cases_path"]}.')


def triage_command(state, args):
    """Handle everything after the word 'triage'."""
    if not args:
        raise ValueError(f'Missing subcommand. {TRIAGE_USAGE}')
    sub, rest = args[0], args[1:]

    if sub == 'load':
        if not rest:
            raise ValueError('Missing path. Usage: triage load <path>')
        load_symptoms_command(state, ' '.join(rest))
        return

    if sub not in ('symptoms', 'new', 'list', 'show', 'update', 'urgent'):
        raise ValueError(f'Unknown triage command "{sub}". {TRIAGE_USAGE}')
    if sub == 'list':
        triage.show_list(state['cases'])
        return
    if sub == 'show':
        if not rest:
            raise ValueError('Missing id. Usage: triage show <id>')
        triage.show_case(state['cases'], ' '.join(rest))
        return
    if sub == 'urgent':
        triage.show_urgent(state['cases'])
        return
    if state['symptoms'] is None:
        raise ValueError('No symptom list is loaded. Use: triage load <path>')

    if sub == 'update':
        if not rest:
            raise ValueError('Missing id. Usage: triage update <id>')
        if state['atlas'] is None:
            raise ValueError('No atlas is loaded. Use: atlas load <path>')
        if not state['cases_ok']:
            raise ValueError(f'{state["cases_path"]} could not be read, so no case can be saved.')
        triage.update_case(state, ' '.join(rest))
    elif sub == 'symptoms':
        commands.show_symptoms(state['symptoms'])
    elif sub == 'new':
        if state['atlas'] is None:
            raise ValueError('No atlas is loaded. Use: atlas load <path>')
        if not state['cases_ok']:
            raise ValueError(f'{state["cases_path"]} could not be read, so no new case can be saved.')
        triage.new_case(state)


def lesion_command(state, args):
    """Handle everything after the word 'lesion'."""
    if not args:
        raise ValueError(f'Missing subcommand. {LESION_USAGE}')
    sub, rest = args[0], args[1:]
    if sub not in ('block', 'risk', 'tree'):
        raise ValueError(f'Unknown lesion command "{sub}". {LESION_USAGE}')
    atlas = state['atlas']
    if atlas is None:
        raise ValueError('No atlas is loaded. Use: atlas load <path>')

    if sub == 'block':
        if not rest:
            raise ValueError('Missing pipe. Usage: lesion block <pipe>')
        commands.lesion_block(atlas, ' '.join(rest))
    elif sub == 'tree':
        if not rest:
            raise ValueError('Missing pipe. Usage: lesion tree <pipe>')
        commands.lesion_tree(atlas, ' '.join(rest))
    else:
        if not rest:
            raise ValueError('Missing area. Usage: lesion risk <area>')
        commands.lesion_risk(atlas, ' '.join(rest))


def main():
    state = {'atlas': None, 'path': None, 'symptoms': None, 'symptoms_path': None,
             'cases': [], 'next_case_number': 1,
             'cases_path': DEFAULT_CASES, 'cases_ok': True,
             'roads': None, 'roads_path': None, 'hospitals': [], 'hospitals_path': None}     # what the program currently remembers
    print('Synapse 1.0 - type "help" to see all commands')
    load_command(state, DEFAULT_ATLAS)        # the atlas loads when the program starts
    load_symptoms_command(state, DEFAULT_SYMPTOMS)   # so does the symptom list
    load_cases_command(state)                 # and every saved case
    load_map_command(state, DEFAULT_ROADS)    # and the map: roads first,
    load_map_command(state, DEFAULT_HOSPITALS)   # then hospitals (they need the roads)

    while True:
        try:
            line = input('synapse> ')
        except EOFError:
            break
        words = line.split()
        if not words:
            continue

        if words[0] == 'exit':
            break
        elif words[0] == 'help':
            print('Commands:\n  atlas load <path>\n  atlas pipes\n  atlas areas\n'
                  '  atlas show <name>\n  atlas find <word>\n  atlas tree\n  atlas path <area>\n  lesion block <pipe>\n  lesion risk <area>\n  lesion tree <pipe>\n  triage symptoms\n  triage new\n  triage list\n  triage show <id>\n  triage update <id>\n  triage urgent\n  triage load <path>\n  map load <path>\n  map roads\n  map hospitals\n  map coverage\n  route from <city>\n  route <case id>\n  route whatif <city> <ability>\n  help\n  exit')
        elif words[0] in ('atlas', 'lesion', 'triage', 'map', 'route', 'unit'):
            handler = {'atlas': atlas_command, 'lesion': lesion_command,
                       'triage': triage_command, 'map': map_command, 'route': route_command, 'unit': unit_command}[words[0]]
            try:
                handler(state, words[1:])
            except ValueError as error:       # a mistake by the user, not a crash
                print(f'ERROR: {error}')
        else:
            print(f'ERROR: Unknown command "{line.strip()}".')


if __name__ == '__main__':
    main()
