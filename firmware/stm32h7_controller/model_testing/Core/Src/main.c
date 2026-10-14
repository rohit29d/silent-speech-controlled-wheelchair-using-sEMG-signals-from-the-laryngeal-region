/* USER CODE BEGIN Header */
/**
 * @file           : main.c
 * @brief          : UART Wheelchair Control with Ultrasonic Safety & Heartbeat
 */
/* USER CODE END Header */

#include "main.h"

/* --- Private Defines --- */
#define OBSTACLE_THRESHOLD 50.0f
#define HEARTBEAT_TIMEOUT 500 // Stop motors if no UART data for 500ms

/* --- Global Variables --- */
UART_HandleTypeDef huart3;
uint8_t rx_buffer[1] = {'0'};
float dist_f = 400.0f;
float dist_b = 400.0f;
uint32_t last_cmd_tick = 0;

/* --- Function Prototypes --- */
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART3_UART_Init(void);
void Control_Wheelchair(char command);
void Set_Motor_Right(int state);
void Set_Motor_Left(int state);
void Motor_Stop(void);

// Sensor Logic Prototypes
void DWT_Init(void);
void delay_us(uint32_t us);
float Get_Distance(GPIO_TypeDef *TrigPort, uint16_t TrigPin,
                   GPIO_TypeDef *EchoPort, uint16_t EchoPin);

int main(void) {
  HAL_Init();
  SystemClock_Config();

  /* Enable Clocks */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_USART3_CLK_ENABLE();

  MX_GPIO_Init();
  MX_USART3_UART_Init();
  DWT_Init();

  BSP_LED_Init(LED_GREEN);
  BSP_LED_Init(LED_RED);

  /* 1. ENABLE BTS7960 DRIVERS */
  HAL_GPIO_WritePin(GPIOE, GPIO_PIN_7 | GPIO_PIN_8 | GPIO_PIN_10 | GPIO_PIN_12,
                    GPIO_PIN_SET);

  /* 2. STARTUP DIAGNOSTIC (Ready Blink + Brief Motor Pulse) */
  for (int i = 0; i < 6; i++) {
    BSP_LED_Toggle(LED_GREEN);
    HAL_Delay(100);
  }

  while (1) {
    /* 3. LISTEN FOR UART DATA (Non-blocking check) */
    if (HAL_UART_Receive(&huart3, rx_buffer, 1, 10) == HAL_OK) {
      last_cmd_tick = HAL_GetTick(); // Reset safety heartbeat
      BSP_LED_Toggle(LED_GREEN);
      Control_Wheelchair(rx_buffer[0]);
    }

    /* 4. SAFETY HEARTBEAT (Stop if Python crashes) */
    if ((HAL_GetTick() - last_cmd_tick) > HEARTBEAT_TIMEOUT) {
      Motor_Stop();
      rx_buffer[0] = '0'; // Reset buffer to neutral
    }

    /* 5. SENSOR UPDATE (Safety Reflex) */
    dist_f = Get_Distance(GPIOE, GPIO_PIN_5, GPIOE, GPIO_PIN_6);
    dist_b = Get_Distance(GPIOC, GPIO_PIN_10, GPIOC, GPIO_PIN_11);

    /* 6. REAL-TIME OBSTACLE OVERRIDE */
    if ((rx_buffer[0] == 'F' && dist_f < OBSTACLE_THRESHOLD) ||
        (rx_buffer[0] == 'B' && dist_b < OBSTACLE_THRESHOLD)) {
      Motor_Stop();
    }

    /* 7. VISUAL FEEDBACK */
    if (dist_f < OBSTACLE_THRESHOLD)
      BSP_LED_On(LED_RED);
    else
      BSP_LED_Off(LED_RED);
  }
}

void Control_Wheelchair(char command) {
  if (command >= 'a' && command <= 'z')
    command -= 32;

  switch (command) {
  case 'F':
    if (dist_f > OBSTACLE_THRESHOLD) {
      Set_Motor_Right(1);
      Set_Motor_Left(1);
    } else {
      Motor_Stop();
    }
    break;
  case 'B':
    if (dist_b > OBSTACLE_THRESHOLD) {
      Set_Motor_Right(-1);
      Set_Motor_Left(-1);
    } else {
      Motor_Stop();
    }
    break;
  case 'L':
    Set_Motor_Right(1);
    Set_Motor_Left(-1);
    break;
  case 'R':
    Set_Motor_Right(-1);
    Set_Motor_Left(1);
    break;
  default:
    Motor_Stop();
    break;
  }
}

void Motor_Stop(void) {
  Set_Motor_Right(0);
  Set_Motor_Left(0);
}

/* --- BTS7960 Driver Implementation --- */

void Set_Motor_Right(int state) {
  if (state == 1) { // Forward
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_11, GPIO_PIN_RESET);
  } else if (state == -1) { // Backward
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_11, GPIO_PIN_SET);
  } else { // Stop
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_11, GPIO_PIN_RESET);
  }
}

void Set_Motor_Left(int state) {
  if (state == 1) { // Forward
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_13, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_14, GPIO_PIN_RESET);
  } else if (state == -1) { // Backward
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_13, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_14, GPIO_PIN_SET);
  } else { // Stop
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_13, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_14, GPIO_PIN_RESET);
  }
}

/* --- Sensor Measurement Logic --- */

float Get_Distance(GPIO_TypeDef *TrigPort, uint16_t TrigPin,
                   GPIO_TypeDef *EchoPort, uint16_t EchoPin) {
  uint32_t start_tick, end_tick;
  uint32_t timeout = 50000; // Reduced timeout for faster loop

  HAL_GPIO_WritePin(TrigPort, TrigPin, GPIO_PIN_SET);
  delay_us(10);
  HAL_GPIO_WritePin(TrigPort, TrigPin, GPIO_PIN_RESET);

  while (HAL_GPIO_ReadPin(EchoPort, EchoPin) == GPIO_PIN_RESET && timeout--)
    ;
  start_tick = DWT->CYCCNT;
  timeout = 50000;
  while (HAL_GPIO_ReadPin(EchoPort, EchoPin) == GPIO_PIN_SET && timeout--)
    ;
  end_tick = DWT->CYCCNT;

  if (timeout == 0)
    return 400.0f;
  return ((float)(end_tick - start_tick) / (SystemCoreClock / 1000000) *
          0.0343f) /
         2.0f;
}

void DWT_Init(void) {
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CYCCNT = 0;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

void delay_us(uint32_t us) {
  uint32_t startTick = DWT->CYCCNT;
  uint32_t delayTicks = us * (SystemCoreClock / 1000000);
  while (DWT->CYCCNT - startTick < delayTicks)
    ;
}

/* --- Initialization (USART, GPIO, Clock) --- */
static void MX_USART3_UART_Init(void) {
  huart3.Instance = USART3;
  huart3.Init.BaudRate = 115200;
  huart3.Init.WordLength = UART_WORDLENGTH_8B;
  huart3.Init.StopBits = UART_STOPBITS_1;
  huart3.Init.Parity = UART_PARITY_NONE;
  huart3.Init.Mode = UART_MODE_TX_RX;
  huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart3.Init.OverSampling = UART_OVERSAMPLING_16;
  HAL_UART_Init(&huart3);
}

static void MX_GPIO_Init(void) {
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* Motor Pins (Port E) */
  GPIO_InitStruct.Pin = GPIO_PIN_7 | GPIO_PIN_8 | GPIO_PIN_9 | GPIO_PIN_10 |
                        GPIO_PIN_11 | GPIO_PIN_12 | GPIO_PIN_13 | GPIO_PIN_14 |
                        GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

  /* Echo Pins */
  GPIO_InitStruct.Pin = GPIO_PIN_6;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

  /* UART PD8/PD9 */
  GPIO_InitStruct.Pin = GPIO_PIN_8 | GPIO_PIN_9;
  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
  GPIO_InitStruct.Alternate = GPIO_AF7_USART3;
  HAL_GPIO_Init(GPIOD, &GPIO_InitStruct);
}

void SystemClock_Config(void) {
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInitStruct = {0};
  HAL_PWREx_ConfigSupply(PWR_LDO_SUPPLY);
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);
  while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {
  }
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_DIV1;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  HAL_RCC_OscConfig(&RCC_OscInitStruct);
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2 |
                                RCC_CLOCKTYPE_D3PCLK1 | RCC_CLOCKTYPE_D1PCLK1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.SYSCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB3CLKDivider = RCC_APB3_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_APB1_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_APB2_DIV1;
  RCC_ClkInitStruct.APB4CLKDivider = RCC_APB4_DIV1;
  HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1);
  PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USART3;
  PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI;
  HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct);
}

void Error_Handler(void) {
  __disable_irq();
  while (1) {
  }
}
