# kohd_translator/kohd_core/glyph_builder.py
from .kohd_rules import LETTER_TO_NODE_INFO, NODE_POSITIONS, NODE_LAYOUT

class KohdGlyphBuilder:
    def __init__(self):
        self.rules = { # Encapsulate rules for clarity
            'letter_to_node_info': LETTER_TO_NODE_INFO,
            'node_positions': NODE_POSITIONS,
            'node_layout': NODE_LAYOUT
        }
        self.reset()

    def reset(self):
        """Resets the builder for a new word."""
        self.current_word_string = ""
        self.active_node_name = None
        self.first_node_name = None
        # This will store the node name from which the most recent *completed* trace originated.
        # Or the first node if no traces yet.
        self.last_trace_origin_node_name = None
        
        self.subnode_queue = []
        self.used_nodes_in_word = set()
        self.glyph_elements = []
        self.is_finalized = False

    def add_letter(self, letter: str):
        """Processes a new letter added to the word."""
        letter = letter.upper()
        if letter not in self.rules['letter_to_node_info']:
            print(f"Warning: Letter '{letter}' not in Kohd alphabet.")
            return False

        self.current_word_string += letter
        self.is_finalized = False
        self._rebuild_glyph_elements_for_string() 
        return True

    def _rebuild_glyph_elements_for_string(self):
        """Internal method to reconstruct glyph_elements based on current_word_string."""
        # Reset temporary build state
        self.glyph_elements = []
        _current_active_node_name = None # Node for the letter currently being processed or last processed
        _first_node_name_for_word = None
        _subnode_queue_for_current_trace = []
        _used_nodes_this_rebuild = set()
        # _last_node_that_originated_a_trace will be _current_active_node_name *before* it's updated to a new distinct node

        if not self.current_word_string:
            self.reset_internal_build_state_vars() # Update main instance vars
            return

        for i, char_code in enumerate(self.current_word_string):
            letter = char_code.upper()
            letter_info = self.rules['letter_to_node_info'][letter]
            target_node_for_letter = letter_info['node_name']
            subnode_info_for_letter = {'letter': letter, 'count': letter_info['subnodes']}

            # Prepare data for the node element (might be new or updating an existing one)
            node_element_data = {
                'type': 'node',
                'name': target_node_for_letter,
                'coords': self.rules['node_positions'][target_node_for_letter],
                'is_active': False, # Will be set true for the final active node at the end
                'has_ring': False
            }

            if i == 0: # First letter
                _first_node_name_for_word = target_node_for_letter
                _current_active_node_name = target_node_for_letter
                
                node_element_data['is_active'] = True # Tentatively
                self._add_or_update_node_element_during_rebuild(node_element_data)
                
                _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                _used_nodes_this_rebuild.add(target_node_for_letter)
            
            else: # Subsequent letters
                if target_node_for_letter == _current_active_node_name:
                    # Letter is in the same node as the previous one
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                    # Ensure this node is marked correctly if it needs a ring (though less likely here)
                    # and ensure it exists in glyph_elements
                    node_element_data['is_active'] = True # Tentatively
                    if target_node_for_letter in _used_nodes_this_rebuild and len(_used_nodes_this_rebuild) > 0 : # Check if it was already used *and left*
                         # This condition for ring on same node might need refinement if a node is left and returned to immediately
                         pass # Ring logic primarily for *returning* to a *different* previously used node
                    self._add_or_update_node_element_during_rebuild(node_element_data)

                else: # Letter is in a new distinct node, a trace is formed
                    # The node we are tracing FROM is the one that was _current_active_node_name
                    from_node_for_trace = _current_active_node_name
                    
                    # Determine if the TO_NODE for the trace needs a ring
                    needs_ring_on_to_node = target_node_for_letter in _used_nodes_this_rebuild
                    
                    self.glyph_elements.append({
                        'type': 'trace',
                        'from_node_name': from_node_for_trace,
                        'to_node_name': target_node_for_letter,
                        'subnodes_on_trace': list(_subnode_queue_for_current_trace),
                        'needs_ring_on_to_node': needs_ring_on_to_node
                    })
                    _subnode_queue_for_current_trace.clear()
                    
                    # The old _current_active_node_name is no longer the "tip" or "active writing point"
                    # Its 'is_active' status will be false unless it's the very last node later.
                    # (Handled by final loop below)

                    _current_active_node_name = target_node_for_letter # Update active node

                    node_element_data['is_active'] = True # Tentatively
                    node_element_data['has_ring'] = needs_ring_on_to_node
                    self._add_or_update_node_element_during_rebuild(node_element_data)
                    
                    _subnode_queue_for_current_trace.append(subnode_info_for_letter)
                    _used_nodes_this_rebuild.add(target_node_for_letter)
        
        # Update main instance variables after iterating through the whole string
        self.active_node_name = _current_active_node_name
        self.first_node_name = _first_node_name_for_word
        self.subnode_queue = _subnode_queue_for_current_trace # This will hold subnodes for the last segment
        self.used_nodes_in_word = _used_nodes_this_rebuild
        
        # Final pass to ensure only the true current active node is marked 'is_active'
        # And ensure all used nodes exist in glyph_elements with correct ring status
        all_node_names_in_elements = set()
        for element in self.glyph_elements:
            if element['type'] == 'node':
                element['is_active'] = (element['name'] == self.active_node_name)
                all_node_names_in_elements.add(element['name'])
        
        # Add any nodes that were part of traces but might not have been explicitly added
        # (e.g. if a trace leads TO a node that wasn't subsequently active for subnode queuing)
        for node_name_used in self.used_nodes_in_word:
            if node_name_used not in all_node_names_in_elements:
                 is_ringed = any(trace['to_node_name'] == node_name_used and trace['needs_ring_on_to_node'] for trace in self.glyph_elements if trace['type'] == 'trace')
                 self._add_or_update_node_element_during_rebuild({
                    'type': 'node',
                    'name': node_name_used,
                    'coords': self.rules['node_positions'][node_name_used],
                    'is_active': (node_name_used == self.active_node_name),
                    'has_ring': is_ringed # Check if any trace leading to it required a ring
                })


    def _add_or_update_node_element_during_rebuild(self, node_data_to_add):
        """Helper for _rebuild_glyph_elements_for_string.
        Adds a node if not present or updates its 'has_ring' status if already there and new data indicates a ring.
        'is_active' is tentative here and finalized at the end of _rebuild.
        """
        existing_node = next((n for n in self.glyph_elements if n['type'] == 'node' and n['name'] == node_data_to_add['name']), None)
        if existing_node:
            if node_data_to_add.get('has_ring', False):
                existing_node['has_ring'] = True
            # is_active will be set globally at the end of _rebuild
        else:
            self.glyph_elements.append(node_data_to_add) # Add the new node data

    def reset_internal_build_state_vars(self):
        """Updates the main instance variables based on a reset/empty string."""
        self.active_node_name = None
        self.first_node_name = None
        self.last_trace_origin_node_name = None
        self.subnode_queue = []
        self.used_nodes_in_word = set()

    def finalize_word(self):
        """Finalizes the current word: adds charge, ground, null modifier checks."""
        if not self.current_word_string or self.is_finalized:
            return

        # 1. Add final trace for any remaining subnodes in queue (to ground indicator position)
        if self.subnode_queue and self.active_node_name:
             self.glyph_elements.append({
                'type': 'trace_to_ground',
                'from_node_name': self.active_node_name,
                'subnodes_on_trace': list(self.subnode_queue),
            })
        
        # 2. Add ground indicator
        if self.active_node_name: # Should always be true if there's a word
            self.glyph_elements.append({
                'type': 'ground_indicator',
                'node_name': self.active_node_name 
            })

        # 3. Add charge indicator
        if self.first_node_name:
            self.glyph_elements.append({
                'type': 'charge_indicator',
                'node_name': self.first_node_name
            })
        
        self.is_finalized = True
        # Deactivate the last active node visually after finalization
        for element in self.glyph_elements:
            if element['type'] == 'node' and element['name'] == self.active_node_name:
                element['is_active'] = False
                break


    def get_glyph_elements(self):
        """Returns the list of elements to be drawn."""
        return self.glyph_elements

    # Placeholder for null modifier logic
    # def _requires_null_modifier(self): # This will be called by finalize_word
    #     # Implement bounding box logic here later
    #     pass

if __name__ == '__main__':
    builder = KohdGlyphBuilder()
    
    word_to_test = "MOTHERBOARD" 
    # word_to_test = "HI"
    # word_to_test = "ME"
    # word_to_test = "MOM"
    print(f"Building word: {word_to_test}")
    for letter_idx, letter_char in enumerate(word_to_test):
        builder.add_letter(letter_char)
        print(f"\n--- After adding '{letter_char}' (String: '{builder.current_word_string}') ---")
        print(f"  Builder State:")
        print(f"    Active Node: {builder.active_node_name}")
        print(f"    First Node: {builder.first_node_name}")
        print(f"    Subnode Queue (for next trace/ground): {builder.subnode_queue}") # Clarified queue purpose
        print(f"    Used Nodes This Rebuild: {builder.used_nodes_in_word}")
        print(f"  Glyph Elements ({len(builder.get_glyph_elements())}):")
        for i, element in enumerate(builder.get_glyph_elements()):
            if element['type'] == 'trace':
                subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
                print(f"    {i+1}. {element['type']}: {element['from_node_name']} -> {element['to_node_name']} (Subs: {subs_str}), RingOnTo: {element.get('needs_ring_on_to_node', False)}")
            elif element['type'] == 'node':
                 print(f"    {i+1}. {element['type']}: {element['name']} (Active: {element.get('is_active', False)}, Ring: {element.get('has_ring', False)})")
            # ADDED THIS ELIF FOR BETTER 'trace_to_ground' PRINTING
            elif element['type'] == 'trace_to_ground':
                subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
                print(f"    {i+1}. {element['type']}: from {element['from_node_name']} (Subs: {subs_str})")
            else:
                print(f"    {i+1}. {element}")


    builder.finalize_word()
    print("\n--- After finalization: ---")
    print(f"  Glyph Elements ({len(builder.get_glyph_elements())}):")
    for i, element in enumerate(builder.get_glyph_elements()):
        if element['type'] == 'trace':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. {element['type']}: {element['from_node_name']} -> {element['to_node_name']} (Subs: {subs_str}), RingOnTo: {element.get('needs_ring_on_to_node', False)}")
        elif element['type'] == 'node':
            print(f"    {i+1}. {element['type']}: {element['name']} (Active: {element.get('is_active', False)}, Ring: {element.get('has_ring', False)})")
        # ADDED THIS ELIF FOR BETTER 'trace_to_ground' PRINTING IN FINALIZATION OUTPUT
        elif element['type'] == 'trace_to_ground':
            subs_str = "".join([s['letter'] for s in element.get('subnodes_on_trace', [])])
            print(f"    {i+1}. {element['type']}: from {element['from_node_name']} (Subs: {subs_str})")
        else:
            print(f"    {i+1}. {element}")