# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS

class KohdGlyphBuilder:
    def __init__(self):
        self.rules = {
            'letter_to_node_info': LETTER_TO_NODE_INFO,
            'node_positions': NODE_POSITIONS,
        }
        self.reset()

    def reset(self):
        self.current_word_string = ""
        self.active_node_name = None # Name of the node for the last processed letter
        self.first_node_name = None  # Name of the first node in the word
        self.subnode_queue = []      # Subnodes for the current active segment (leading to next distinct node or ground)
        self.glyph_elements = []     # List of dicts: nodes, traces, indicators
        self.is_finalized = False

    def _get_or_create_node_element_data(self, node_name, node_elements_data_map):
        """Ensures a node's data dict exists in the map, creating if not."""
        if node_name not in node_elements_data_map:
            node_elements_data_map[node_name] = {
                'type': 'node',
                'name': node_name,
                'coords': self.rules['node_positions'][node_name],
                'is_active': False, # Managed globally at the end of rebuild
                'ring_count': 0     # Actual number of rings this node will display
            }
        return node_elements_data_map[node_name]

    def _rebuild_glyph_elements_for_string(self):
        self.glyph_elements = []
        # This map will store the live data for nodes as we build, including their current ring_count
        current_node_data_map = {} 

        _current_processing_active_node_name = None # Node for the current letter being processed
        _first_node_name_for_this_word = None
        _subnode_queue_for_current_trace = []
        # Tracks nodes that have had their initial letter sequence processed and a trace has moved *away* from them.
        _nodes_that_have_been_departed_from = set()

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

            # Ensure node data exists for the target node
            target_node_data = self._get_or_create_node_element_data(target_node_name_for_letter, current_node_data_map)

            if i == 0: # First letter
                _first_node_name_for_this_word = target_node_name_for_letter
                _current_processing_active_node_name = target_node_name_for_letter
                _subnode_queue_for_current_trace.append(subnode_info_for_letter)
            else: # Subsequent letters
                if target_node_name_for_letter == _current_processing_active_node_name:
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                else: # Moving to a new distinct node
                    from_node_name_for_trace = _current_processing_active_node_name
                    from_node_data = current_node_data_map[from_node_name_for_trace] # Should exist

                    _nodes_that_have_been_departed_from.add(from_node_name_for_trace)

                    # Determine connection levels for the trace
                    # Origin connection level is the current ring_count of the from_node
                    origin_connect_ring_level = from_node_data.get('ring_count', 0)
                    
                    # Target connection level is the current ring_count of the to_node
                    # *before* it's potentially incremented by this return
                    target_connect_ring_level = target_node_data.get('ring_count', 0)

                    # If this move to target_node_name_for_letter is a "return"
                    is_return_to_target_node = target_node_name_for_letter in _nodes_that_have_been_departed_from
                    
                    self.glyph_elements.append({
                        'type': 'trace',
                        'from_node_name': from_node_name_for_trace,
                        'to_node_name': target_node_name_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace),
                        'connect_from_ring_level': origin_connect_ring_level,
                        'connect_to_ring_level': target_connect_ring_level
                    })
                    _subnode_queue_for_current_trace.clear()
                    
                    # If it was a return, increment the target node's actual ring_count for future display/traces
                    if is_return_to_target_node:
                        target_node_data['ring_count'] = target_connect_ring_level + 1
                    
                    _current_processing_active_node_name = target_node_name_for_letter
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
        
        # After loop, finalize instance variables
        self.active_node_name = _current_processing_active_node_name
        self.first_node_name = _first_node_name_for_this_word
        self.subnode_queue = list(_subnode_queue_for_current_trace)

        # Add all processed node data objects to self.glyph_elements
        # Ensure their 'is_active' flag is set correctly
        for node_name, data in current_node_data_map.items():
            data['is_active'] = (node_name == self.active_node_name)
            # Check if already added by _get_or_create... (it should be, this is more of a formal transfer)
            if not any(el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == node_name):
                 self.glyph_elements.append(data) # Should not happen if _get_or_create always adds
            else: # Update existing one if necessary (though _get_or_create returns reference)
                existing_el = next(el for el in self.glyph_elements if el['type'] == 'node' and el['name'] == node_name)
                existing_el.update(data)

    def add_letter(self, letter: str):
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']:
            print(f"Warning: Letter '{letter}' not in Kohd alphabet.")
            return False # Indicate failure or invalid letter

        self.current_word_string += letter
        self.is_finalized = False # Adding a letter un-finalizes
        self._rebuild_glyph_elements_for_string() # This handles the core logic
        return True

    def finalize_word(self):
        if not self.current_word_string or self.is_finalized:
            return

        if self.subnode_queue and self.active_node_name:
            active_node_data = next((n for n in self.glyph_elements if n['type']=='node' and n['name'] == self.active_node_name), None)
            origin_ring_level_for_ground_trace = active_node_data.get('ring_count', 0) if active_node_data else 0

            self.glyph_elements.append({
                'type': 'trace_to_ground',
                'from_node_name': self.active_node_name,
                'subnodes_on_trace': list(self.subnode_queue),
                'connect_from_ring_level': origin_ring_level_for_ground_trace
            })
        
        if self.active_node_name:
            self.glyph_elements.append({'type': 'ground_indicator', 'node_name': self.active_node_name})
        if self.first_node_name:
            self.glyph_elements.append({'type': 'charge_indicator', 'node_name': self.first_node_name})
        
        self.is_finalized = True
        if self.active_node_name:
            for el in self.glyph_elements:
                if el['type'] == 'node' and el['name'] == self.active_node_name:
                    el['is_active'] = False; break
        self.subnode_queue.clear()

    def get_glyph_elements(self):
        return list(self.glyph_elements)


if __name__ == '__main__':
    builder = KohdGlyphBuilder()
    # word_to_test = "MOTHERBOARD"
    # word_to_test = "MOM" 
    # word_to_test = "ABA" # MNO(A) -> ABC(B) -> MNO(A, connect_to_target_ring_level=0, MNO ring_count becomes 1)
    word_to_test = "ABACA" 
    # Expected for ABACA:
    # A (MNO, rc0) -> B (ABC, rc0) - trace1 (MNO:rc0 -> ABC:rc0)
    # B (ABC, rc0) -> A (MNO, rc0 initially) - trace2 (ABC:rc0 -> MNO:rc0), MNO rc becomes 1
    # A (MNO, rc1) -> C (JKL, rc0) - trace3 (MNO:rc1 -> JKL:rc0)
    # C (JKL, rc0) -> A (MNO, rc1 initially) - trace4 (JKL:rc0 -> MNO:rc1), MNO rc becomes 2

    print(f"Building word: {word_to_test}")
    for letter_char in word_to_test: # Simulate typing
        builder.add_letter(letter_char)

    # Print state before finalization to see intermediate structure
    print(f"\n--- Glyph Elements Before Finalization for '{builder.current_word_string}' ({len(builder.get_glyph_elements())}) ---")
    for i, element in enumerate(builder.get_glyph_elements()):
        if element['type'] == 'node':
            print(f"    {i+1}. NODE: {element['name']} (Active: {element.get('is_active', False)}, Rings: {element.get('ring_count', 0)})")
        elif element['type'] == 'trace':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. TRACE: {element['from_node_name']}(R{element.get('connect_from_ring_level')}) -> {element['to_node_name']}(R{element.get('connect_to_ring_level')}) (Subs: {subs_str})")
        else:
            print(f"    {i+1}. {element}")

    builder.finalize_word()
    print(f"\n--- Glyph Elements After Finalization for '{builder.current_word_string}' ({len(builder.get_glyph_elements())}) ---")
    # Similar detailed printout for finalized state
    for i, element in enumerate(builder.get_glyph_elements()):
        if element['type'] == 'node':
            print(f"    {i+1}. NODE: {element['name']} (Active: {element.get('is_active', False)}, Rings: {element.get('ring_count', 0)})")
        elif element['type'] == 'trace':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. TRACE: {element['from_node_name']}(R{element.get('connect_from_ring_level')}) -> {element['to_node_name']}(R{element.get('connect_to_ring_level')}) (Subs: {subs_str})")
        elif element['type'] == 'trace_to_ground':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. TRACE_TO_GROUND: from {element['from_node_name']}(R{element.get('connect_from_ring_level')}) (Subs: {subs_str})")
        else:
            print(f"    {i+1}. {element}")