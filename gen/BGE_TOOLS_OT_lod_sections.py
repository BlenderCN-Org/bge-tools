import bge, os, pickle

PROP_NAME = "BGE_TOOLS_LOD_SECTIONS"

class LODSections(bge.types.KX_GameObject):
	
	sections = []
	
	def __init__(self, own):
		self.copy_custom_normals()
		
	def copy_custom_normals(self):
		if not (PROP_NAME in self and self[PROP_NAME]):
			return
			
		dir_path = bge.logic.expandPath("//" + PROP_NAME)
		if not os.path.exists(dir_path):
			print("Warning:", dir_path, "does not exist.")
			
		file_path = os.path.join(dir_path, self.name + ".txt")
		with open(file_path, "rb") as f:
			normals = pickle.load(f)
			
		for ob_name, ob_normals in normals.items():
			ob = self.scene.objects[ob_name]
			mesh = ob.meshes[0]
			
			for mat_id in range(mesh.numMaterials):
				for vert_id in range(mesh.getVertexArrayLength(mat_id)):
					vert = mesh.getVertex(mat_id, vert_id)
					id = str([round(f) for f in vert.XYZ.xy])
					if id in ob_normals:
						vert.normal = ob_normals[id]
						
	def update(self):
		sections = [sect.name for sect in self.children if sect.currentLodLevel == 0]
		for sect in list(self.sections):
			if sect not in sections:
				self.sections.remove(sect)
				# set to no collision
		for sect in sections:
			if sect not in self.sections:
				self.sections.append(sect)
				# set to static
				
def get_mutated(cls, cont):
	obj = cont.owner
	if isinstance(obj, cls):
		return obj
		
	mutated_obj = cls(obj)
	assert(obj is not mutated_obj)
	assert(obj.invalid)
	assert(mutated_obj is cont.owner)
	
	return mutated_obj
	
def update(cont):
	lod_sections = get_mutated(LODSections, cont)
	lod_sections.update()
	