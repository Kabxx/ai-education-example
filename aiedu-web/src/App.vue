<script setup lang="ts">
import *  as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import Live2d from './components/Live2d.vue'

// 挂载PIXI到全局
(window as any).PIXI = PIXI;
// 启动Ticker
Live2DModel.registerTicker(PIXI.Ticker);
</script>

<template>
  <Live2d />
</template>
