/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    stm32h7xx_it.c
  * @brief   Interrupt Service Routines.
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32h7xx_it.h"

/* External variables --------------------------------------------------------*/
/* USER CODE BEGIN EV */
/* This tells the interrupt file that huart3 is defined in main.c */
extern UART_HandleTypeDef huart3;
/* USER CODE END EV */

/******************************************************************************/
/* Cortex Processor Interruption and Exception Handlers          */
/******************************************************************************/

void NMI_Handler(void) { while (1) {} }
void HardFault_Handler(void) { while (1) {} }
void MemManage_Handler(void) { while (1) {} }
void BusFault_Handler(void) { while (1) {} }
void UsageFault_Handler(void) { while (1) {} }
void SVC_Handler(void) {}
void DebugMon_Handler(void) {}
void PendSV_Handler(void) {}

void SysTick_Handler(void)
{
  HAL_IncTick();
}

/******************************************************************************/
/* STM32H7xx Peripheral Interrupt Handlers                                    */
/******************************************************************************/

/**
  * @brief This function handles EXTI line[15:10] interrupts.
  */
void EXTI15_10_IRQHandler(void)
{
  BSP_PB_IRQHandler(BUTTON_USER);
}

/**
  * @brief This function handles USART3 global interrupt.
  */
void USART3_IRQHandler(void)
{
  /* This calls the HAL internal state machine to handle the data reception */
  HAL_UART_IRQHandler(&huart3);
}

/* USER CODE BEGIN 1 */
/* You can leave this empty now as the logic is in the handler above */
/* USER CODE END 1 */
