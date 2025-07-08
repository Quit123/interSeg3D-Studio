<template>
  <v-dialog
      v-model="dialog"
      :fullscreen="display.xs"
      max-width="800px"
      persistent
      scrollable
  >
    <v-card>
      <v-card-title class="headline">
        Pre Segmentation Results
        <v-spacer></v-spacer>
        <v-btn icon @click="closeDialog">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-divider></v-divider>

      <v-card-text class="segmentation-content">
        <div v-if="props.loading" class="loading-container">
          <v-progress-circular
              color="primary"
              indeterminate
              size="64"
          ></v-progress-circular>
          <p class="mt-4">Segmenting objects, please wait...</p>
          <p class="text-caption">This may take a minute as the system renders and processes multiple views.</p>
        </div>

        <div v-else-if="props.results.length === 0" class="no-results">
          <v-icon color="grey lighten-1" x-large>mdi-alert-circle-outline</v-icon>
          <h3 class="mt-4">No segment results available</h3>
          <p>There may be some errors in pre segmentation part.</p>
        </div>

        <div v-else class="d-flex flex-wrap justify-center">
          <div
            v-for="(imgPath, idx) in props.results"
            :key="idx"
            class="ma-4"
            style="max-width: 320px;"
          >
            <v-img
              :src="imgPath"
              aspect-ratio="1.5"
              contain
              class="rounded"
            ></v-img>
            <div class="text-center mt-2 grey--text text--darken-1">
              {{ imgPath.split('/').pop() }}
            </div>
          </div>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="justify-end">
        <v-btn
            class="mr-2"
            color="error"
            dense
            text
            @click="closeDialog"
        >
          Close
        </v-btn>
      
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import {computed, PropType} from 'vue';
import {useDisplay} from 'vuetify';

// Props definition
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  results: {
    type: Array as PropType<string[]>,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
});

// Emit events
const emit = defineEmits(['update:modelValue']);

// Get display breakpoints from Vuetify
const display = useDisplay();

// Computed for dialog visibility
const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

// Methods
function closeDialog() {
  dialog.value = false;
}
</script>

<style scoped>
.segmentation-content {
  min-height: 300px;
  overflow-y: auto; /* Keep this if you want scrolling for very large content */
  display: flex;
  flex-direction: column;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  text-align: center;
}

.no-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  text-align: center;
  color: #757575;
}
</style>