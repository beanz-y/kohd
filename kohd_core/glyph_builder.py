# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS, NODE_LAYOUT

class KohdGlyphBuilder:
    def __init__(self):
        self.rules = {
            'letter_to_node_info': LETTER_TO_NODE_INFO,
            'node_positions': NODE_POSITIONS,
            'node_layout': NODE_LAYOUT
        }
        self.reset()

    def reset(self):
        self.current_word_string = ""
        self.active_node_name = None
        self.first_node_name = None
        self.subnode_queue = []
        self.used_nodes_in_word_initial_activation = set() # Tracks nodes upon their first activation sequence
        self.glyph_elements = [] # List of dicts representing drawable elements
        self.is_finalized = False

    def add_letter(self, letter: str):
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']:
            print(f"Warning: Letter '{letter}' not in Kohd alphabet.")
            return False

        self.current_word_string += letter
        self.is_finalized = False
        self._rebuild_glyph_elements_for_string()
        return True

    def _get_or_create_node_element_in_glyph(self, node_name, node_elements_map):
        """Finds an existing node element or creates and adds a new one."""
        if node_name not in node_elements_map:
            new_node_element = {
                'type': 'node',
                'name': node_name,
                'coords': self.rules['node_positions'][node_name],
                'is_active': False,
                'ring_count': 0
            }
            self.glyph_elements.append(new_node_element)
            node_elements_map[node_name] = new_node_element
        return node_elements_map[node_name]

    def _rebuild_glyph_elements_for_string(self):
        self.glyph_elements = [] # Start fresh for drawable elements
        node_elements_map = {}   # Helper to quickly access node elements by name {'MNO': node_dict_ref}
        
        _current_word_active_node_name = None
        _first_node_name_for_this_word = None
        _subnode_queue_for_current_trace = []
        # Tracks nodes that have completed their first sequence of letter processing.
        # A node is added here when a trace *leaves* it, or it's the first node and a different node is processed.
        _nodes_activated_and_left = set() 

        if not self.current_word_string:
            self.active_node_name = None
            self.first_node_name = None
            self.subnode_queue = []
            return

        for i, char_code in enumerate(self.current_word_string):
            letter = char_code.upper()
            letter_info = self.rules['letter_to_node_info'][letter]
            target_node_name_for_letter = letter_info['node_name']
            subnode_info_for_letter = {'letter': letter, 'count': letter_info['subnodes']}

            # Ensure the target node exists in our glyph_elements list (via map)
            target_node_element = self._get_or_create_node_element_in_glyph(target_node_name_for_letter, node_elements_map)

            if i == 0: # First letter
                _first_node_name_for_this_word = target_node_name_for_letter
                _current_word_active_node_name = target_node_name_for_letter
                _subnode_queue_for_current_trace.append(subnode_info_for_letter)
            else: # Subsequent letters
                if target_node_name_for_letter == _current_word_active_node_name:
                    # Still in the same node
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                else: # Moving to a new distinct node
                    from_node_for_trace = _current_word_active_node_name
                    
                    # Add current active node to "activated and left" set
                    _nodes_activated_and_left.add(from_node_for_trace)

                    # If the target_node_name_for_letter has been "activated and left" before, it's a return.
                    is_return_to_target_node = target_node_name_for_letter in _nodes_activated_and_left
                    
                    if is_return_to_target_node:
                        target_node_element['ring_count'] = target_node_element.get('ring_count', 0) + 1
                        
                    self.glyph_elements.append({
                        'type': 'trace',
                        'from_node_name': from_node_for_trace,
                        'to_node_name': target_node_name_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace)
                        # Ring visual is on the node element itself via 'ring_count'
                    })
                    _subnode_queue_for_current_trace.clear()
                    
                    _current_word_active_node_name = target_node_name_for_letter
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)

        # Update instance state variables
        self.active_node_name = _current_word_active_node_name
        self.first_node_name = _first_node_name_for_this_word
        self.subnode_queue = list(_subnode_queue_for_current_trace) # Store remaining queue

        # Set the 'is_active' flag correctly on the final active node in glyph_elements
        for element in self.glyph_elements:
            if element['type'] == 'node':
                element['is_active'] = (element['name'] == self.active_node_name)

    def finalize_word(self):
        if not self.current_word_string or self.is_finalized:
            return

        # The active_node_name already reflects the last node processed by _rebuild.
        # The subnode_queue contains subnodes for that last active segment.
        if self.subnode_queue and self.active_node_name:
            self.glyph_elements.append({
                'type': 'trace_to_ground',
                'from_node_name': self.active_node_name,
                'subnodes_on_trace': list(self.subnode_queue),
            })
        
        if self.active_node_name:
            self.glyph_elements.append({
                'type': 'ground_indicator',
                'node_name': self.active_node_name 
            })

        if self.first_node_name:
            self.glyph_elements.append({
                'type': 'charge_indicator',
                'node_name': self.first_node_name
            })
        
        # TODO: Null Modifier Logic based on bounding box of used nodes
        # For now, just ensure all nodes involved are in glyph_elements with final states
        # The _rebuild logic should handle adding all necessary nodes.

        self.is_finalized = True
        # Deactivate the active node visually after finalization
        if self.active_node_name:
            active_node_el = next((el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == self.active_node_name), None)
            if active_node_el:
                active_node_el['is_active'] = False
        
        self.subnode_queue.clear() # Clear queue after it's used for trace_to_ground

    def get_glyph_elements(self):
        return list(self.glyph_elements) # Return a copy


if __name__ == '__main__':
    builder = KohdGlyphBuilder()
    
    # word_to_test = "MOTHERBOARD"
    # word_to_test = "MOM" # Should have 0 rings on MNO
    word_to_test = "COMMUNICATION" # Expected to show rings on MNO, STU, GHI
    
    print(f"Building word: {word_to_test}")
    for letter_idx, letter_char in enumerate(word_to_test):
        builder.add_letter(letter_char)
        # Optional: Print detailed state after each letter if needed for debugging
        # print(f"\n--- After adding '{letter_char}' (String: '{builder.current_word_string}') ---")
        # print(f"  Builder State: Active: {builder.active_node_name}, First: {builder.first_node_name}, Queue: {builder.subnode_queue}")
        # print(f"  Glyph Elements (Intermediate - {len(builder.get_glyph_elements())}):")
        # for i, element in enumerate(builder.get_glyph_elements()):
        #     print(f"    {i+1}. {element}")


    print(f"\n--- Glyph Elements Before Finalization for '{builder.current_word_string}' ({len(builder.get_glyph_elements())}) ---")
    for i, element in enumerate(builder.get_glyph_elements()):
        if element['type'] == 'trace':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. {element['type']}: {element['from_node_name']} -> {element['to_node_name']} (Subs: {subs_str})")
        elif element['type'] == 'node':
            print(f"    {i+1}. {element['type']}: {element['name']} (Active: {element.get('is_active', False)}, Rings: {element.get('ring_count', 0)})")
        else:
            print(f"    {i+1}. {element}")

    builder.finalize_word()
    print(f"\n--- Glyph Elements After Finalization for '{builder.current_word_string}' ({len(builder.get_glyph_elements())}) ---")
    for i, element in enumerate(builder.get_glyph_elements()):
        if element['type'] == 'trace':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. {element['type']}: {element['from_node_name']} -> {element['to_node_name']} (Subs: {subs_str})")
        elif element['type'] == 'trace_to_ground':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. {element['type']}: from {element['from_node_name']} (Subs: {subs_str})")
        elif element['type'] == 'node':
            print(f"    {i+1}. {element['type']}: {element['name']} (Active: {element.get('is_active', False)}, Rings: {element.get('ring_count', 0)})")
        else:
            print(f"    {i+1}. {element}")