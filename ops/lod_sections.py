import bpy, bmesh, math
from mathutils import Vector, Matrix
from collections import OrderedDict
from . import utils as ut

ERR_MSG_WRONG_OBJECT = "Selected object not suited for this application"
ERR_MSG_WRONG_LAYER = "Selected object not in active layer"
ERR_MSG_NO_OBJECT_SELECTED = "No object selected"
ERR_MSG_NO_ACTIVE_OBJECT_SELECTED = "No active object selected"

PARTICLES = "_PARTICLES"
VERTEX_GROUP = "_BOUNDS"
TEMP_SUFFIX = "_TEMP"
BASE_SUFFIX = "_BASE"
SECT_SUFFIX = "_SECT"
LOD_SUFFIX = "_LOD"
PHYSICS_SUFFIX = "_PHYSICS"
NUMB_SUFFIX = ".000"
PROP_NAME = "BGE_TOOLS_LOD_SECTIONS"
SCRIPT_NAME = PROP_NAME.lower()

class LODSections(bpy.types.Operator):
	
	bl_description = "Generates sections with level of detail"
	bl_idname = "bge_tools.lod_sections"
	bl_label = "BGE-Tools: LOD Sections"
	bl_options = {"REGISTER", "UNDO", "PRESET"}
	
	prop_update_or_clear = bpy.props.EnumProperty(items=[("update", "Update", ""), ("clear", "Clear", "")], name="", default="update")
	prop_number_or_size = bpy.props.EnumProperty(items=[("generate_by_number", "Number", ""), ("generate_by_size", "Size", "")], name="Generate by", default="generate_by_number")
	prop_number = bpy.props.IntVectorProperty(name="", description="Number of sections", min=1, soft_max=128, default=(8, 8), size=2)
	prop_size = bpy.props.FloatVectorProperty(name="", description="Section size", min=1, soft_max=128, default=(8, 8), size=2)
	prop_number_mode = bpy.props.EnumProperty(items=[("use_automatic_numbering", "Use Automatic Numbering", ""), ("use_even_numbers", "Use Even Numbers", ""), ("use_odd_numbers", "Use Odd Numbers", "")], name="", default="use_even_numbers")
	prop_decimate_dissolve = bpy.props.BoolProperty(name="Decimate Dissolve", default=True)
	prop_decimate_dissolve_angle_limit = bpy.props.FloatProperty(name="", min=0, max=math.pi, default=math.radians(1), subtype="ANGLE")
	prop_lod = bpy.props.BoolProperty(name="Level of detail", default=True)
	prop_lod_number = bpy.props.IntProperty(name="", min=1, max=8, default=4)
	prop_lod_factor = bpy.props.FloatProperty(name="", min=0, max=1, default=0.25, subtype="FACTOR")
	prop_gen_options = bpy.props.EnumProperty(items=[("generate_sections", "Generate Sections", ""), ("generate_sections_and_save_json_file", "Generate Sections and Save Json File", "")], name="", default="generate_sections_and_save_json_file")
	prop_approx = bpy.props.BoolProperty(name="Approximate", default=True)
	prop_approx_num_digits = bpy.props.IntProperty(name="", min=0, max=15, default=2)
	
	err_msg = ""
	log_msg = ""
	
	def invoke(self, context, event):
		
		if context.object in context.selected_editable_objects:
			if isinstance(context.object.data, bpy.types.Mesh):
				self.scene = context.scene
				self.object = context.object
			else:
				self.err_msg = ERR_MSG_WRONG_OBJECT
		elif context.selected_editable_objects:
			self.err_msg = ERR_MSG_NO_ACTIVE_OBJECT_SELECTED
		elif context.selected_objects:
			self.err_msg = ERR_MSG_WRONG_LAYER
		else:
			self.err_msg = ERR_MSG_NO_OBJECT_SELECTED
			
		system_dpi = bpy.context.user_preferences.system.dpi
		
		return context.window_manager.invoke_props_dialog(self, width=system_dpi*5)
		
	def draw(self, context):
		
		layout = self.layout
		box = layout.box
		row = box().row
		
		if self.log_msg:
			row().label(self.log_msg, icon="INFO")
			return
			
		if self.err_msg:
			row().label(self.err_msg, icon="CANCEL")
			return
			
		if PROP_NAME in self.object.game.properties:
			row().prop(self, "prop_update_or_clear")
			return
			
		row().prop(self, "prop_number_or_size")
		
		col = row().column
		col_numb = col()
		col_numb.prop(self, "prop_number")
		col_size = col()
		col_size.prop(self, "prop_size")
		col_size.prop(self, "prop_number_mode")
		
		if self.prop_number_or_size == "generate_by_number":
			col_size.active = False
		else:
			col_numb.active = False
			
		col = row().column
		col().prop(self, "prop_decimate_dissolve")
		col_deci = col()
		col_deci.prop(self, "prop_decimate_dissolve_angle_limit")
		if not self.prop_decimate_dissolve:
			col_deci.active = False
			
		col = row().column
		col().prop(self, "prop_lod")
		col_lod = col()
		col_lod.prop(self, "prop_lod_number")
		col_lod.prop(self, "prop_lod_factor")
		if not self.prop_lod:
			col_lod.active = False
			
		col = row().column
		col_appr = col()
		col_appr.prop(self, "prop_approx")
		col_ndig = col()
		col_ndig.prop(self, "prop_approx_num_digits")
		
		if self.prop_gen_options == "generate_sections":
			col_appr.active = False
			col_ndig.active = False
		elif not self.prop_approx:
			col_ndig.active = False
			
	def check(self, context):
		
		if self.err_msg:
			return False
		return True
		
	def execute(self, context):
		
		if self.err_msg:
			return {"CANCELLED"}
			
		if PROP_NAME in self.object.game.properties:
			
			for i, prop in enumerate(self.object.game.properties):
				if prop.name == PROP_NAME:
					bpy.ops.object.game_property_remove(i)
					
			ut.remove_logic_python(self.object, SCRIPT_NAME)
			ut.remove_text_internal(SCRIPT_NAME)
			
			for sect in self.object.children:
				for sect_lod in sect.children:
					ut.remove(sect_lod)
				ut.remove(sect)
				
			self.object.hide_render = False
			self.object.draw_type = "TEXTURED"
			
			if self.prop_update_or_clear == "clear":
				return {"FINISHED"}
				
		print("\nLOD Sections\n------------\n")
		
		def initialize():
			
			bpy.ops.object.mode_set(mode="OBJECT")
			self.cursor_location = self.scene.cursor_location.copy()
			
			self.prof = ut.Profiler()
			
			self.number = Vector()
			self.size = Vector()
			
			dimensions = ut.dimensions(self.object).xy
			
			if self.prop_number_or_size == "generate_by_number":
				self.number.x = self.prop_number[0]
				self.number.y = self.prop_number[1]
				self.size.x = dimensions.x / self.number.x
				self.size.y = dimensions.y / self.number.y
			else:
				self.size.x = self.prop_size[0]
				self.size.y = self.prop_size[1]
				n_x = math.ceil(dimensions.x / self.size.x)
				n_y = math.ceil(dimensions.y / self.size.y)
				
				numb_mode = self.prop_number_mode
				if numb_mode == "use_automatic_numbering":
					self.number.x = n_x
					self.number.y = n_y
				else:
					i = 0 if numb_mode == "use_even_numbers" else 1
					self.number.x = n_x + 1 - i if n_x % 2 else n_x + i
					self.number.y = n_y + 1 - i if n_y % 2 else n_y + i
					
			self.ndigits = len(str(int(self.number.x * self.number.y)))
			self.points = OrderedDict()
			
			n = 1
			for j in range(int(self.number.y)):
				y = 0.5 * self.size.y * (2 * j + 1 - self.number.y)
				for i in range(int(self.number.x)):
					x = 0.5 * self.size.x * (2 * i + 1 - self.number.x)
					id = ut.get_id(n, "", self.ndigits)
					self.points[id] = Vector((x, y, 0))
					n += 1
					
			self.particles = {}
			self.sections = {}
			
			bpy.ops.object.duplicate()
			self.object.select = False
			
			self.base = self.scene.objects.active
			self.base.name = self.object.name + BASE_SUFFIX
			self.base.data.name = self.object.data.name + BASE_SUFFIX
			
			self.base.game.physics_type = "NO_COLLISION"
			self.materials = set(self.base.data.materials)
			
			for mod in self.base.modifiers:
				
				if mod.type == "PARTICLE_SYSTEM":
					bpy.ops.object.modifier_remove(modifier=mod.name)
					continue
					
				print(self.prof.timed("Applying ", mod.name))
				
				bpy.ops.object.modifier_apply(apply_as="DATA", modifier=mod.name)
				
			bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
			bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
			self.transform = self.base.matrix_world.copy()
			self.base.matrix_world = Matrix()
			
			bpy.ops.object.editmode_toggle()
			bpy.ops.mesh.select_all()
			bpy.ops.mesh.quads_convert_to_tris()
			bpy.ops.mesh.select_all(action="DESELECT")
			bpy.ops.object.editmode_toggle()
			
		def dissolve():
			
			if not self.prop_decimate_dissolve:
				return
				
			print(self.prof.timed("Applying Decimate Dissolve"))
			
			bpy.ops.object.editmode_toggle()
			bpy.ops.mesh.select_all()
			
			bpy.ops.mesh.dissolve_limited(angle_limit=self.prop_decimate_dissolve_angle_limit, use_dissolve_boundaries=False, delimit={"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"})
			
			bpy.ops.mesh.quads_convert_to_tris()
			bpy.ops.mesh.beautify_fill()
			
			bpy.ops.mesh.select_all(action="DESELECT")
			bpy.ops.object.editmode_toggle()
			
		def generate_sections():
			
			print(self.prof.timed("Multisecting base"))
			
			bpy.ops.object.duplicate()
			self.base.select = False
			
			tmps = self.scene.objects.active
			tmps.name = self.object.name + TEMP_SUFFIX + NUMB_SUFFIX
			tmps.data.name = self.object.data.name + TEMP_SUFFIX + NUMB_SUFFIX
			tmps.vertex_groups.new(VERTEX_GROUP)
			tmps.show_all_edges = True
			tmps.show_wire = True
			
			bpy.ops.object.editmode_toggle()
			
			bm = bmesh.from_edit_mesh(tmps.data)
			
			for i in range(int(self.number.x) + 1):
				try:
					l = bm.verts[:] + bm.edges[:] + bm.faces[:]
					co = ((i - 0.5 * self.number.x) * self.size.x, 0, 0)
					no = (1, 0, 0)
					d = bmesh.ops.bisect_plane(bm, geom=l, plane_co=co, plane_no=no)
					bmesh.ops.split_edges(bm, edges=[e for e in d["geom_cut"] if isinstance(e, bmesh.types.BMEdge)])
				except RuntimeError:
					continue
					
			for i in range(int(self.number.y) + 1):
				try:
					l = bm.verts[:] + bm.edges[:] + bm.faces[:]
					co = (0, (i - 0.5 * self.number.y) * self.size.y, 0)
					no = (0, 1, 0)
					d = bmesh.ops.bisect_plane(bm, geom=l, plane_co=co, plane_no=no)
					bmesh.ops.split_edges(bm, edges=[e for e in d["geom_cut"] if isinstance(e, bmesh.types.BMEdge)])
				except RuntimeError:
					continue
					
			bmesh.update_edit_mesh(tmps.data)
			
			bpy.ops.object.editmode_toggle()
			
			bm.free()
			del bm
			
			print(self.prof.timed("Separating into sections"))
			
			bpy.ops.mesh.separate(type="LOOSE")
			tmps = context.selected_objects
			bpy.ops.object.select_all(action="DESELECT")
			
			print(self.prof.timed("Organizing sections"))
			
			for tmp in tmps:
				self.scene.objects.active = tmp
				tmp.select = True
				
				bpy.ops.object.editmode_toggle()
				bpy.ops.mesh.select_all()
				bpy.ops.mesh.remove_doubles()
				bpy.ops.mesh.quads_convert_to_tris()
				bpy.ops.mesh.beautify_fill()
				bpy.ops.mesh.region_to_loop()
				bpy.ops.object.vertex_group_assign()
				bpy.ops.mesh.select_all(action="DESELECT")
				bpy.ops.object.editmode_toggle()
				
				bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
				
				inside = False
				for id, v in self.points.items():
					if ut.point_inside_rectangle(tmp.location, (v, self.size * 0.99)):
						tmp.name = self.object.name + SECT_SUFFIX + id
						tmp.data.name = self.object.data.name + SECT_SUFFIX + id
						self.scene.cursor_location = v
						bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
						self.sections[id] = tmp
						tmp.select = False
						inside = True
						break
						
				if not inside:
					ut.remove(tmp)
					
		def generate_lod():
			
			if not (self.prop_lod and self.prop_lod_number > 1):
				return
				
			lod_dist = round(math.pi * math.sqrt(self.size.x * self.size.y) * 0.5)
			self.scene.cursor_location = zero_loc = Vector()
			id = ut.get_id(0, "", self.ndigits) + ut.get_id(self.prop_lod_number - 1, ".", 1)
			sect_lod_me_linked_name = self.object.data.name + SECT_SUFFIX + id
			sect_lod_me_linked = bpy.data.meshes.new(sect_lod_me_linked_name)
			
			for i in range(self.prop_lod_number):
				
				print(self.prof.timed("Generating LOD ", i + 1, " of ", self.prop_lod_number))
				
				lod_id = ut.get_id(i, ".", 1)
				
				for sect in self.sections.values():
					sect_lod_name = sect.name + LOD_SUFFIX + lod_id
					sect_lod_me_name = sect.data.name + LOD_SUFFIX + lod_id
					
					if i == self.prop_lod_number - 1:
						sect_lod = bpy.data.objects.new(sect_lod_name, sect_lod_me_linked)
						self.scene.objects.link(sect_lod)
						
						sect_lod.draw_type = "BOUNDS"
						sect_lod.hide_render = True
						sect_lod.hide = True
					else:
						self.scene.objects.active = sect
						sect.select = True
						bpy.ops.object.duplicate()
						sect.select = False
						
						sect_lod = self.scene.objects.active
						sect_lod.name = sect_lod_name
						sect_lod.data.name = sect_lod_me_name
						sect_lod.location.xyz = zero_loc
						
					mod_decimate_collapse = sect_lod.modifiers.new("Decimate Collapse", "DECIMATE")
					mod_decimate_collapse.decimate_type = "COLLAPSE"
					mod_decimate_collapse.ratio = self.prop_lod_factor / (i + 1)
					mod_decimate_collapse.vertex_group = VERTEX_GROUP
					mod_decimate_collapse.invert_vertex_group = True
					#mod_decimate_collapse.use_collapse_triangulate = True
					bpy.ops.object.modifier_apply(apply_as="DATA", modifier="Decimate Collapse")
					
					sect_lod.parent = sect
					sect_lod.select = False
					
					self.scene.objects.active = sect
					sect.select = True
					bpy.ops.object.lod_add()
					lod_level = sect.lod_levels[len(sect.lod_levels) - 1]
					lod_level.distance = lod_dist * (i + 1)
					lod_level.use_material = True
					lod_level.object = sect_lod
					sect.select = False
					
		def convert_particles():
			
			particles = {}
			
			for mod in self.object.modifiers:
				if mod.type == "PARTICLE_SYSTEM":
					
					if not mod.show_viewport:
						continue
						
					settings = mod.particle_system.settings
					
					if not settings.dupli_object:
						continue
						
					print(self.prof.timed("Converting ", mod.name))
					
					self.materials.update(settings.dupli_object.data.materials)
					
					self.scene.objects.active = self.object
					self.object.select = True
					bpy.ops.object.duplicates_make_real()
					self.object.select = False
					bpy.ops.object.make_single_user(type="SELECTED_OBJECTS", obdata=True)
					
					transform_inverted = self.transform.inverted()
					for ob in context.selected_objects:
						ob.matrix_world = transform_inverted * ob.matrix_world
						
						inside = False
						for id, v in self.points.items():
							if ut.point_inside_rectangle(ob.location, (v, self.size)):
								if id not in particles:
									particles[id] = []
								particles[id].append(ob)
								inside = True
								break
								
						if not inside:
							ut.remove(ob)
							
					bpy.ops.object.select_all(action="DESELECT")
					mod.show_viewport = mod.show_render = False
					
			for id, objects in particles.items():
				self.particles[id] = p = objects[0]
				p.data.name = p.name = self.object.name + PARTICLES + id
				
				if not objects:
					continue
					
				if len(objects) > 1:
					self.scene.objects.active = p
					meshes = []
					for ob in objects:
						ob.select = True
						if ob == p:
							continue
						meshes.append(ob.data)
					bpy.ops.object.join()
					p.select = False
					for me in meshes:
						ut.remove(me)
						
		def join_particles():
			
			if not self.particles:
				return
				
			for id, sect in self.sections.items():
				
				if id not in self.particles:
					continue
					
				v = self.points[id]
				part = self.particles[id]
				part_me = part.data
				for j, sect_lod in enumerate(sect.children[:-1]):
					self.scene.objects.active = part
					part.select = True
					bpy.ops.object.duplicate()
					part.select = False
					part_lod = self.scene.objects.active
					part_lod_me = part_lod.data
					
					mod_decimate_collapse = part_lod.modifiers.new("Decimate Collapse", "DECIMATE")
					mod_decimate_collapse.decimate_type = "COLLAPSE"
					mod_decimate_collapse.ratio = self.prop_lod_factor / (j + 1)
					mod_decimate_collapse.use_collapse_triangulate = True
					bpy.ops.object.modifier_apply(apply_as="DATA", modifier="Decimate Collapse")
					
					self.scene.objects.active = sect_lod
					sect_lod.select = True
					bpy.ops.object.join()
					self.scene.cursor_location = v
					bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
					sect_lod.select = False
					
					ut.remove(part_lod_me)
					
				self.scene.objects.active = sect
				sect.select = True
				part.select = True
				bpy.ops.object.join()
				self.scene.cursor_location = v
				bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
				sect.select = False
				
				ut.remove(part_me)
				
		def copy_normals():
			
			objects = []
			for sect in self.sections.values():
				objects.append(sect)
				for sect_lod in sect.children[:-1]:
					objects.append(sect_lod)
					
			for ob in objects:
				self.scene.objects.active = ob
				ob.select = True
				
				ob.data.use_auto_smooth = True
				ob.data.create_normals_split()
				
				mod_copy_cust_norm = ob.modifiers.new(name="Copy Custom Normals", type="DATA_TRANSFER")
				mod_copy_cust_norm.object = self.base
				mod_copy_cust_norm.use_loop_data = True
				mod_copy_cust_norm.data_types_loops = {"CUSTOM_NORMAL"}
				mod_copy_cust_norm.vertex_group = VERTEX_GROUP
				
				bpy.ops.object.modifier_apply(apply_as="DATA", modifier="Copy Custom Normals")
				
				ob.select = False
				
			ut.remove(self.base)
			
		def finalize():
			
			print(self.prof.timed("Finalizing sections"))
			
			materials_lod = {}
			
			for mat in self.materials:
				mat_lod = mat.copy()
				mat_lod.name = mat.name + LOD_SUFFIX
				materials_lod[mat.name] = mat_lod
				
				mat_lod.game_settings.physics = False
				mat_lod.use_cast_shadows = False
				mat_lod.use_shadows = False
				
				mat.game_settings.physics = True
				mat.use_cast_shadows = True
				mat.use_shadows = True
				
			for sect in self.sections.values():
				for sect_lod in sect.children:
					for i, mat in enumerate(sect_lod.data.materials):
						sect_lod.active_material_index = i
						sect_lod.active_material = materials_lod[mat.name]
				sect.parent = self.object
				
		def export_normals():
			
			print(self.prof.timed("Exporting custom normals"))
			
			approx_ndigits = self.prop_approx_num_digits if self.prop_approx else -1
			
			custom_normals = {}
			
			objects = []
			for sect in self.sections.values():
				objects.append(sect)
				for sect_lod in sect.children[:-1]:
					objects.append(sect_lod)
					
			for ob in objects:
				self.scene.objects.active = ob
				ob.select = True
				
				bpy.ops.object.editmode_toggle()
				bpy.ops.mesh.select_all(action="DESELECT")
				bpy.ops.object.vertex_group_select()
				bpy.ops.object.editmode_toggle()
				
				custom_normals[ob.name] = ut.get_custom_normals(ob, approx_ndigits, True)
				
				bpy.ops.object.editmode_toggle()
				bpy.ops.mesh.select_all(action="DESELECT")
				bpy.ops.object.editmode_toggle()
				
				ob.vertex_groups.remove(ob.vertex_groups.get(VERTEX_GROUP))
				
				ob.select = False
				
			ut.save_txt(custom_normals, PROP_NAME, self.object.name)
			
		def restore_initial_state():
			
			print(self.prof.timed("Restoring initial state"))
			
			for sect in self.sections.values():
				
				for sect_lod in sect.children:
					sect_lod.hide_render = True
					sect_lod.hide = True
					
			self.scene.cursor_location = self.cursor_location
			self.scene.objects.active = self.object
			self.object.select = True
			self.object.hide = False
			self.object.hide_render = True
			self.object.draw_type = "BOUNDS"
						
		def generate_game_logic():
			
			print(self.prof.timed("Generating game logic"))
			
			if PROP_NAME not in self.object:
				bpy.ops.object.game_property_new(type="BOOL", name=PROP_NAME)
			else:
				self.object[PROP_NAME].type = "BOOL"
			self.object.game.properties[PROP_NAME].value = True
			
			ut.add_text(self.bl_idname, True, SCRIPT_NAME)
			ut.add_logic_python(self.object, SCRIPT_NAME, "update", True)
			
		def log():
			
			self.log_msg = self.prof.timed("Finished generating ", len(self.sections), " (", round(self.size.x, 1), " X ", round(self.size.y, 1), ") sections in")
			
			print(self.log_msg)
			
		initialize()
		dissolve()
		generate_sections()
		generate_lod()
		convert_particles()
		join_particles()
		copy_normals()
		finalize()
		export_normals()
		restore_initial_state()
		generate_game_logic()
		log()
		
		return {"FINISHED"}
		
def register():
	bpy.utils.register_class(LODSections)
	
def unregister():
	bpy.utils.unregister_class(LODSections)
	
if __name__ == "__main__":
	register()
	