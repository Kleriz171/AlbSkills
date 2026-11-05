"""Synapse: the program you start. Commands: atlas load / pipes / areas / show / find."""

import commands
from loader import AtlasError, load_atlas
from symptoms import SymptomError, load_symptoms

DEFAULT_ATLAS = 'data/atlas.txt'
DEFAULT_SYMPTOMS = 'data/symptoms.txt'
TRIAGE_USAGE = 'Usage: triage load <path> | symptoms'
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

    if sub not in ('symptoms',):
        raise ValueError(f'Unknown triage command "{sub}". {TRIAGE_USAGE}')
    if state['symptoms'] is None:
        raise ValueError('No symptom list is loaded. Use: triage load <path>')

    if sub == 'symptoms':
        commands.show_symptoms(state['symptoms'])


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
    state = {'atlas': None, 'path': None, 'symptoms': None, 'symptoms_path': None}     # what the program currently remembers
    print('Synapse 1.0 - type "help" to see all commands')
    load_command(state, DEFAULT_ATLAS)        # the atlas loads when the program starts
    load_symptoms_command(state, DEFAULT_SYMPTOMS)   # so does the symptom list

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
                  '  atlas show <name>\n  atlas find <word>\n  atlas tree\n  atlas path <area>\n  lesion block <pipe>\n  lesion risk <area>\n  lesion tree <pipe>\n  help\n  exit')
        elif words[0] in ('atlas', 'lesion', 'triage'):
            handler = {'atlas': atlas_command, 'lesion': lesion_command,
                       'triage': triage_command}[words[0]]
            try:
                handler(state, words[1:])
            except ValueError as error:       # a mistake by the user, not a crash
                print(f'ERROR: {error}')
        else:
            print(f'ERROR: Unknown command "{line.strip()}".')


if __name__ == '__main__':
    main()
