<template>
  <div class="container max">
    <button @click="connect">连接</button>
    <canvas ref="canvas"></canvas>
    <div>未完成的字幕?</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';
import { blobToArrayBuffer } from '@/utils/lang';

const canvas = ref<HTMLCanvasElement>(); // canvas元素的引用
let app: PIXI.Application;// Pixi应用的引用
let model: Live2DModel; // Live2D模型的引用
let ws: WebSocket; // WebSocket的引用
let audioContext: AudioContext; // 音频上下文的引用

const initPixiApplication = async () => {
  // 初始化Pixi应用
  const application = new PIXI.Application({
    view: canvas.value!,
    autoStart: true,
  });
  // 保存引用
  app = application;
};

const initLive2dModel = async () => {
  // 加载Live2D模型
  const live2dModel = await Live2DModel.from('/models/UG/ugofficial.model3.json');
  // 设置模型的交互模式
  live2dModel.autoInteract = false;
  // 设置模型的位置和缩放
  live2dModel.scale.set(0.5);
  live2dModel.anchor.set(-0.35, -0.2);
  // 保存引用
  model = live2dModel;
};

const initWebsocket = async () => {
  let header: any = null;
  // 创建WebSocket连接
  const websocket = new WebSocket('ws://localhost:8080');
  // 连接成功的回调
  websocket.onopen = () => {
    console.log('WebSocket连接成功');
    ws = websocket;
  };
  // 连接失败的回调
  websocket.onerror = async (error) => {
    console.error('WebSocket连接失败，重试中...', error);
    await initWebsocket();
  };
  // 监听消息
  websocket.onmessage = (event) => {
    if (header === null) {
      header = JSON.parse(event.data);
    } else {
      if (header.type === 'audio') {
        playAudio(event.data);
      }
      header = null;
    }
  };
};

const cleanPixiApplication = async () => {
  // 销毁Pixi应用
  app?.destroy();
}

const cleanLive2dModel = async () => {
  // 销毁模型
  model?.destroy();
}

const cleanWebsocket = async () => {
  // 关闭WebSocket连接
  ws?.close();
}

const updateLive2dModelMouth = (
  audioAnalyser: AnalyserNode,
  prevMouthAmlitude: number = 0,
) => {
  // 通过音频分析器获取音频频率数据
  const audioFrequencyArray = new Uint8Array(audioAnalyser.frequencyBinCount);
  audioAnalyser.getByteFrequencyData(audioFrequencyArray);
  const audioVolume = audioFrequencyArray.reduce((acc, cur) => acc + cur, 0) / audioFrequencyArray.length;
  // 计算新的嘴巴张开程度
  const stabilityFactor = 0.2;
  const nextMouthAmlitude = Math.max(0, Math.min(1, (prevMouthAmlitude * stabilityFactor + (audioVolume / 50) * (1 - stabilityFactor))));
  // 平滑过渡
  const smoothFactor = 0.2;
  const updateModelMouthAmlitude = Math.abs(prevMouthAmlitude - nextMouthAmlitude) < smoothFactor ? nextMouthAmlitude : prevMouthAmlitude;
  // 保存上一次的嘴巴张开程度
  prevMouthAmlitude = nextMouthAmlitude;
  // 更新模型的嘴巴张开程度
  (model.internalModel.coreModel as any).setParameterValueById('ParamMouthOpenY', updateModelMouthAmlitude);
  // 递归调用
  if (audioContext.state === 'running') {
    requestAnimationFrame(() => updateLive2dModelMouth(audioAnalyser, nextMouthAmlitude));
  }
}

const playAudio = async (audio: Blob) => {
  try {
    // 读取音频文件
    console.log("播放音频结束");
    const arrayBuffer = await blobToArrayBuffer(audio);
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    const audioSource = audioContext.createBufferSource();
    const audioAnalyser = audioContext.createAnalyser();
    audioAnalyser.connect(audioContext.destination);
    audioSource.buffer = audioBuffer;
    audioSource.connect(audioAnalyser);
    audioSource.start();
    updateLive2dModelMouth(audioAnalyser);
    audioSource.onended = async () => {
      console.log("播放音频开始");
      ws.send(JSON.stringify({ type: 'action', data: 'AUDIO FINISHED' }));
    };
  } catch (error) {
    console.error('播放音频失败', error);
  }
}

const connect = async () => {
  await audioContext.resume()
  await initWebsocket();
}

onMounted(async () => {
  await initPixiApplication();
  await initLive2dModel();
  app!.stage.addChild(model!);
  audioContext = new AudioContext();
});

onUnmounted(async () => {
  await cleanWebsocket();
  app!.stage.removeChild(model!);
  await cleanLive2dModel();
  await cleanPixiApplication();
});

</script>


<style scoped>
.max {
  width: 100%;
  height: 100%;
  /* 使 canvas 元素占满父元素 */
}

canvas {
  width: 50vw;
  height: 75vh;
}

.container {
  display: flex;
  /* 使用 flexbox 布局 */
  flex-direction: column;
  /* 子元素垂直排列 */
  justify-content: center;
  /* 垂直居中 */
  align-items: center;
  /* 水平居中 */
  height: 100vh;
  /* 使容器占满整个视口高度 */
}
</style>