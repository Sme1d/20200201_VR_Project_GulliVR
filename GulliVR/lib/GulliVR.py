#!/usr/bin/python3

# import avango-guacamole libraries
import avango
import avango.gua
import avango.vive
from avango.script import field_has_changed
from lib.Picker import *

# import python libraries
import sys
import time

# renders the given scenegraph\\
class GulliVR(avango.script.Script):
	sf_rocker = avango.SFFloat()
	sf_touchpad_button = avango.SFFloat()
	
	# Declaration of variables
	animating = False
	starting_time = None
	giant_mode_is_active = False
	scene_original = None
	navigation_original = None

	# Declaration of constant variables
	ANIMATION_TIME = 0.5
	NORMAL_SCALE = 50.0
	GIANT_SCALE = 0.02

	def __init__(self):
		self.super(GulliVR).__init__()

	def set_inputs(self, scenegraph, controller_sensor):
		self.scenegraph = scenegraph
		self.scene = self.scenegraph["/scene"]
		self.navigation_node = self.scenegraph["/navigation_node"]
		self.camera_node = self.scenegraph["/navigation_node/Vive-HMD-User"]
		self.picker = Picker(self.scenegraph)
		self.sf_rocker.connect_from(controller_sensor.Value3)
		self.sf_touchpad_button.connect_from(controller_sensor.Value2)
		self.always_evaluate(True)
		self.build_ground_marker()

	def evaluate(self):
		if self.animating:
			self.animate()

		if self.giant_mode_is_active and not self.animating:
			ground_position = self.send_ray()
			if ground_position:
				self.ground_marker.Transform.value = avango.gua.make_trans_mat(ground_position.x,ground_position.y,ground_position.z) * avango.gua.make_scale_mat(.02,.02,.02)

	# Animate mode switching. Direction is determined by current mode
	def animate(self):
		animation_proceded = ((time.time() - self.starting_time) / self.ANIMATION_TIME)
		if self.giant_mode_is_active:
			animation_proceded = ((time.time() - self.starting_time) / self.ANIMATION_TIME) ** 0.2
			reference_scale = self.GIANT_SCALE
			intermediate_scale = 1 - (1-reference_scale) * animation_proceded
		else:
			animation_proceded = ((time.time() - self.starting_time) / self.ANIMATION_TIME) ** 1.5
			reference_scale = self.NORMAL_SCALE
			intermediate_scale = 1 + (reference_scale-1) * animation_proceded

		if animation_proceded >= 1:
			self.scene.Transform.value = self.scene_original * avango.gua.make_scale_mat(reference_scale, reference_scale, reference_scale)
			self.navigation_node.Transform.value = self.navigation_transform
			self.animating = False
			self.starting_time = None
			self.scene_original = None
			if self.giant_mode_is_active:
				self.ground_marker.Tags.value.remove('invisible')
		else:
			intermediate_translation = self.navigation_transform.get_translate() - self.navigation_original.get_translate()
			self.navigation_node.Transform.value = self.navigation_original * avango.gua.make_trans_mat(intermediate_translation.x * animation_proceded, 0, intermediate_translation.z * animation_proceded)
			self.scene.Transform.value = self.scene_original * avango.gua.make_scale_mat(intermediate_scale,intermediate_scale,intermediate_scale)

	# Switching from giant to normal mode and vis-a-vis
	def switch_mode(self):
		if not self.giant_mode_is_active:
			reference_scale = self.GIANT_SCALE
		else:
			reference_scale = self.NORMAL_SCALE
			self.ground_marker.Tags.value.append('invisible')

		self.scene_original = self.scene.Transform.value
		self.navigation_original = self.navigation_node.Transform.value
		distance_to_origin = self.camera_node.WorldTransform.value.get_translate()
		self.navigation_transform = avango.gua.make_trans_mat(distance_to_origin.x * reference_scale, 0.0, distance_to_origin.z * reference_scale)
		navigation_camera_offset = avango.gua.make_trans_mat(self.camera_node.Transform.value.get_translate().x, 0.0, self.camera_node.Transform.value.get_translate().z)	
		self.navigation_transform *= avango.gua.make_inverse_mat(navigation_camera_offset)
		
		self.animating = True
		self.starting_time = time.time()
		self.giant_mode_is_active = not self.giant_mode_is_active

	# Determine ground position by using picker
	def send_ray(self):
		result = self.picker.compute_pick_result(self.camera_node.WorldTransform.value.get_translate(),avango.gua.Vec3(0,-1,0),1000000,[])
		if result:
			return result.WorldPosition.value
		return None

	# Load and builds ground marker
	def build_ground_marker(self):
		loader = avango.gua.nodes.TriMeshLoader()
		self.ground_marker = loader.create_geometry_from_file('ground_marker', 'data/objects/ground_marker.obj', avango.gua.LoaderFlags.DEFAULTS)
		self.ground_marker.Material.value.set_uniform('Color', avango.gua.Vec4(1.0, 0.0, 0.0, 1.0))
		self.ground_marker.Tags.value.append('invisible')
		self.scenegraph.Root.value.Children.value.append(self.ground_marker)

	# Triggers switching of mode by button press
	@field_has_changed(sf_rocker)
	def sf_rocker_button_changed(self):
		if self.sf_rocker.value == 1.0 and not self.animating:
			self.switch_mode()