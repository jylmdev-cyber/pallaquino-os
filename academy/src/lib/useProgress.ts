/** Reactive access to the shared progress store; every island on the page stays in sync through a window event. */
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ProgressStore, emptyState, type ProgressState } from './progress';

let shared: ProgressStore | null = null;

export function progressStore(): ProgressStore {
	if (!shared) shared = new ProgressStore();
	return shared;
}

export function useProgress() {
	const state = ref<ProgressState>(emptyState());
	const ready = ref(false);
	const update = (event: Event) => { state.value = (event as CustomEvent<ProgressState>).detail; };
	onMounted(() => {
		state.value = progressStore().load(); ready.value = true;
		window.addEventListener('pallaquino-progress', update);
	});
	onBeforeUnmount(() => window.removeEventListener('pallaquino-progress', update));
	return { state, ready, store: progressStore };
}
