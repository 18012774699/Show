import gym
import time
import tensorflow as tf
from tensorflow import keras
import numpy as np
from collections import deque

# 声明使用的环境
env = gym.make("Breakout-v0")
obs = env.reset()

keras.backend.clear_session()
tf.random.set_seed(42)
np.random.seed(42)
env.seed(42)

# for _ in range(1000):
#     env.render()
#     time.sleep(0.05)
#     # 随机选择一个动作
#     action = env.action_space.sample()
#     next_state, reward, done, info = env.step(action)

input_shape = env.observation_space.shape  # 观测数据
n_outputs = env.action_space.n  # 可选动作

replay_memory = deque(maxlen=20000)
# activation = keras.layers.LeakyReLU(0.2)
activation = "relu"

model = keras.models.Sequential([
    keras.layers.Conv2D(64, kernel_size=7, strides=2, padding="same", activation=activation,
                        input_shape=input_shape),
    keras.layers.MaxPooling2D(2),
    keras.layers.Conv2D(128, kernel_size=3, padding="same", activation=activation),
    keras.layers.Conv2D(128, kernel_size=3, padding="same", activation=activation),
    keras.layers.MaxPooling2D(2),
    keras.layers.Flatten(),
    keras.layers.Dense(64, activation=activation),
    keras.layers.Dense(32, activation=activation),
    keras.layers.Dense(n_outputs)
])
print(model.summary())


# ε-贪婪策略
def epsilon_greedy_policy(state, epsilon=0):
    if np.random.rand() < epsilon:
        return np.random.randint(2)
    else:
        Q_values = model.predict(state[np.newaxis])
        return np.argmax(Q_values[0])


# 每个经验包含五个元素：状态，智能体选择的动作，奖励，下一个状态，一个知识是否结束的布尔值（done）。
# 需要一个小函数从接力缓存随机采样。返回的是五个NumPy数组，对应五个经验
def sample_experiences(batch_size):
    indices = np.random.randint(len(replay_memory), size=batch_size)
    batch = [replay_memory[index] for index in indices]
    states, actions, rewards, next_states, dones = [
        np.array([experience[field_index] for experience in batch])
        for field_index in range(5)]
    return states, actions, rewards, next_states, dones


# 使用ε-贪婪策略的单次玩游戏函数，然后将结果经验存储在replay_buffer中
def play_one_step(env, state, epsilon):
    action = epsilon_greedy_policy(state, epsilon)
    next_state, reward, done, info = env.step(action)
    replay_memory.append((state, action, reward, next_state, done))
    return next_state, reward, done, info


# 拷贝在线模型，为目标模型
target = keras.models.clone_model(model)
target.set_weights(model.get_weights())

batch_size = 32
discount_rate = 0.95
optimizer = keras.optimizers.Adam(lr=1e-3)
loss_fn = keras.losses.Huber()


def training_step(batch_size):
    experiences = sample_experiences(batch_size)
    states, actions, rewards, next_states, dones = experiences
    next_Q_values = model.predict(next_states)
    best_next_actions = np.argmax(next_Q_values, axis=1)
    next_mask = tf.one_hot(best_next_actions, n_outputs).numpy()
    next_best_Q_values = (target.predict(next_states) * next_mask).sum(axis=1)
    target_Q_values = (rewards + (1 - dones) * discount_rate * next_best_Q_values).reshape(-1, 1)
    mask = tf.one_hot(actions, n_outputs)
    with tf.GradientTape() as tape:
        all_Q_values = model(states)
        Q_values = tf.reduce_sum(all_Q_values * mask, axis=1, keepdims=True)
        loss = tf.reduce_mean(loss_fn(target_Q_values, Q_values))
    grads = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(zip(grads, model.trainable_variables))


rewards = []
best_score = 0

for episode in range(600):
    obs = env.reset()
    for step in range(200):
        epsilon = max(1 - episode / 500, 0.01)
        obs, reward, done, info = play_one_step(env, obs, epsilon)
        if done:
            break
    rewards.append(step)
    if step > best_score:
        best_weights = model.get_weights()
        best_score = step
    print("\rEpisode: {}, Steps: {}, eps: {:.3f}".format(episode, step + 1, epsilon), end="")
    if episode > 50:
        training_step(batch_size)
    if episode % 50 == 0:
        target.set_weights(model.get_weights())
    # Alternatively, you can do soft updates at each step:
    # if episode > 50:
    # target_weights = target.get_weights()
    # online_weights = model.get_weights()
    # for index in range(len(target_weights)):
    #    target_weights[index] = 0.99 * target_weights[index] + 0.01 * online_weights[index]
    # target.set_weights(target_weights)

model.set_weights(best_weights)