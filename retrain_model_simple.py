import asyncio
from enhanced_ai_logic import EnhancedAILogic

async def retrain():
    async with EnhancedAILogic() as ai:
        success = await ai.train_model()
        if success:
            print("Model retrained successfully!")
            model_info = ai.get_model_info()
            print(f"Model info: {model_info}")
        else:
            print("Model retraining failed!")

if __name__ == "__main__":
    asyncio.run(retrain())