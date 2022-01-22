# -*- coding: utf-8 -*-
"""
python+pygameg實現經典的《坦克大战》遊戲
"""
import os
import uuid
import random
import pygame
import time
import threading


class Timer(object):
    """ 計時器，定時執行回調函数"""
    def __init__(self):
        self.timers = []

    def add(self, interval, f, repeat = -1):
        timer = {
            "interval"    : interval,   #調用間隔，單位ms
            "callback"    : f,  #回調函数
            "repeat"        : repeat,   #重複調用次数
            "times"            : 0,     #當前調用次数
            "time"            : 0,      #計時
            "uuid"            : uuid.uuid4()    #唯一id
        }
        self.timers.append(timer)
        return timer["uuid"]

    def destroy(self, uuid_nr):
        for timer in self.timers:
            if timer["uuid"] == uuid_nr:
                self.timers.remove(timer)
                return

    def update(self, time_passed):
        for timer in self.timers:
            timer["time"] += time_passed
            # 夠間隔時間就調用回調函数並重新計時
            if timer["time"] >= timer["interval"]:
                timer["time"] -= timer["interval"]
                timer["times"] += 1
                # 調用次數滿就移除該回調函数的計時器，否則調用該回調函数
                if timer["repeat"] > -1 and timer["times"] == timer["repeat"]:
                    self.timers.remove(timer)
                try:
                    timer["callback"]()
                except:
                    try:
                        self.timers.remove(timer)
                    except:
                        pass


class Castle(object):
    """ 玩家基地 """
    (STATE_STANDING, STATE_DESTROYED, STATE_EXPLODING) = range(3)

    def __init__(self):
        global sprites

        # 未被消滅的玩家基地圖像
        self.img_undamaged = sprites.subsurface(0, 15*2, 16*2, 16*2)
        # 被消滅後的玩家基地圖像
        self.img_destroyed = sprites.subsurface(16*2, 15*2, 16*2, 16*2)

        # 玩家基地位置和大小
        self.rect = pygame.Rect(12*16, 24*16, 32, 32)

        # 初始顯示為未被消滅的玩家基地圖像
        self.rebuild()

    def draw(self):
        """ 畫玩家基地 """
        global screen

        screen.blit(self.image, self.rect.topleft)

        if self.state == self.STATE_EXPLODING:
            # 爆炸完了
            if not self.explosion.active:
                self.state = self.STATE_DESTROYED
                del self.explosion
            # 現在開始爆炸
            else:
                self.explosion.draw()

    def rebuild(self):
        """ 玩家基地 """
        self.state = self.STATE_STANDING
        self.image = self.img_undamaged
        self.active = True

    def destroy(self):
        """ 被炮彈擊毁後的玩家基地 """
        # 標記為爆炸
        self.state = self.STATE_EXPLODING
        self.explosion = Explosion(self.rect.topleft)
        # 基地被擊毀後的圖像
        self.image = self.img_destroyed
        self.active = False


class Bonus(object):
    """
    遊戲中會出現多種寶物
    寶物類型：
        手雷：敵人全滅
        頭盔：暫時無敵
        鐵锹：基地城牆變為鋼板
        星星：火力增强
        坦克：加一條生命
        時鐘：所有敵人暂停一段時間
    """
    # 寶物類型
    (BONUS_GRENADE, BONUS_HELMET, BONUS_SHOVEL, BONUS_STAR, BONUS_TANK, BONUS_TIMER, BONUS_BIGGER) = range(7)

    def __init__(self, level):
        global sprites

        self.level = level

        self.active = True

        # 寶物是否可見
        self.visible = True

        # 隨機生成寶物出現位置
        self.rect = pygame.Rect(random.randint(0, 416-32), random.randint(0, 416-32), 32, 32)

        # 隨機生成出現的寶物類型
        self.bonus = random.choice([
            self.BONUS_GRENADE,
            self.BONUS_HELMET,
            self.BONUS_SHOVEL,
            self.BONUS_STAR,
            self.BONUS_TANK,
            self.BONUS_TIMER
        ])
        # 寶物圖像
        self.image = sprites.subsurface(16*2*self.bonus, 32*2, 16*2, 15*2)

    def draw(self):
        """ 畫寶物到屏幕上 """
        global screen
        if self.visible:
            screen.blit(self.image, self.rect.topleft)

    def toggleVisibility(self):
        """ 切換寶物是否可見 """
        self.visible = not self.visible


class Bullet(object):
    """ 坦克炮彈 """
    # 炮彈方向
    (DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT) = range(4)
    # 砲彈狀態
    (STATE_REMOVED, STATE_ACTIVE, STATE_EXPLODING) = range(3)
    # 砲彈属性，玩家 or 敵人
    (OWNER_PLAYER, OWNER_ENEMY) = range(2)

    def __init__(self, level, position, direction, damage = 100, speed = 5):
        global sprites

        self.level = level
        # 砲彈方向
        self.direction = direction
        # 砲彈傷害
        self.damage = damage

        self.owner = None
        self.owner_class = None

        # 砲彈類型：1為普通砲彈；2為加强的炮彈，可以消滅鋼板
        self.power = 1

        # 砲彈圖像
        self.image = sprites.subsurface(75*2, 74*2, 3*2, 4*2)

        # 重新計算炮彈方向和座標
        if direction == self.DIR_UP:
            self.rect = pygame.Rect(position[0] + 11, position[1] - 8, 6, 8)
        elif direction == self.DIR_RIGHT:
            self.image = pygame.transform.rotate(self.image, 270)
            self.rect = pygame.Rect(position[0] + 26, position[1] + 11, 8, 6)
        elif direction == self.DIR_DOWN:
            self.image = pygame.transform.rotate(self.image, 180)
            self.rect = pygame.Rect(position[0] + 11, position[1] + 26, 6, 8)
        elif direction == self.DIR_LEFT:
            self.image = pygame.transform.rotate(self.image, 90)
            self.rect = pygame.Rect(position[0] - 8 , position[1] + 11, 8, 6)

        # 砲彈爆炸效果圖
        self.explosion_images = [
            sprites.subsurface(0, 80*2, 32*2, 32*2),
            sprites.subsurface(32*2, 80*2, 32*2, 32*2),
        ]
        # 砲彈移動速度
        self.speed = speed

        self.state = self.STATE_ACTIVE

    def draw(self):
        """ 畫砲彈 """
        global screen
        if self.state == self.STATE_ACTIVE:
            screen.blit(self.image, self.rect.topleft)
        elif self.state == self.STATE_EXPLODING:
            self.explosion.draw()

    def update(self):
        global castle, players, enemies, bullets

        if self.state == self.STATE_EXPLODING:
            if not self.explosion.active:
                self.destroy()
                del self.explosion

        if self.state != self.STATE_ACTIVE:
            return

        # 計算砲彈座標，砲彈碰撞牆壁會消失
        if self.direction == self.DIR_UP:
            self.rect.topleft = [self.rect.left, self.rect.top - self.speed]
            if self.rect.top < 0:
                if play_sounds and self.owner == self.OWNER_PLAYER:
                    sounds["steel"].play()
                self.explode()
                return
        elif self.direction == self.DIR_RIGHT:
            self.rect.topleft = [self.rect.left + self.speed, self.rect.top]
            if self.rect.left > (416 - self.rect.width):
                if play_sounds and self.owner == self.OWNER_PLAYER:
                    sounds["steel"].play()
                self.explode()
                return
        elif self.direction == self.DIR_DOWN:
            self.rect.topleft = [self.rect.left, self.rect.top + self.speed]
            if self.rect.top > (416 - self.rect.height):
                if play_sounds and self.owner == self.OWNER_PLAYER:
                    sounds["steel"].play()
                self.explode()
                return
        elif self.direction == self.DIR_LEFT:
            self.rect.topleft = [self.rect.left - self.speed, self.rect.top]
            if self.rect.left < 0:
                if play_sounds and self.owner == self.OWNER_PLAYER:
                    sounds["steel"].play()
                self.explode()
                return

        has_collided = False

        # 砲彈擊中地形
        rects = self.level.obstacle_rects
        collisions = self.rect.collidelistall(rects)
        if collisions != []:
            for i in collisions:
                if self.level.hitTile(rects[i].topleft, self.power, self.owner == self.OWNER_PLAYER):
                    has_collided = True
        if has_collided:
            self.explode()
            return

        #   砲彈相互碰撞，則爆炸並移走該砲彈
        for bullet in bullets:
            if self.state == self.STATE_ACTIVE and bullet.owner != self.owner and bullet != self and self.rect.colliderect(bullet.rect):
                self.destroy()
                self.explode()
                return

        # 砲彈擊中玩家坦克
        for player in players:
            if player.state == player.STATE_ALIVE and self.rect.colliderect(player.rect):
                if player.bulletImpact(self.owner == self.OWNER_PLAYER, self.damage, self.owner_class):
                    self.destroy()
                    return

        # 砲彈擊中對方坦克
        for enemy in enemies:
            if enemy.state == enemy.STATE_ALIVE and self.rect.colliderect(enemy.rect):
                if enemy.bulletImpact(self.owner == self.OWNER_ENEMY, self.damage, self.owner_class):
                    self.destroy()
                    return

        # 砲彈擊中玩家基地
        if castle.active and self.rect.colliderect(castle.rect):
            castle.destroy()
            self.destroy()
            return

    def explode(self):
        """ 砲彈爆炸 """
        global screen
        if self.state != self.STATE_REMOVED:
            self.state = self.STATE_EXPLODING
            self.explosion = Explosion([self.rect.left-13, self.rect.top-13], None, self.explosion_images)

    def destroy(self):
        """ 標記砲彈為移除狀態 """
        self.state = self.STATE_REMOVED


class Label(object):
    def __init__(self, position, text = "", duration = None):
        self.position = position

        self.active = True

        self.text = text

        self.font = pygame.font.SysFont("Arial", 13)

        if duration != None:
            gtimer.add(duration, lambda :self.destroy(), 1)

    def draw(self):
        global screen
        screen.blit(self.font.render(self.text, False, (200,200,200)), \
                    [self.position[0]+4, self.position[1]+8])

    def destroy(self):
        self.active = False


class Explosion(object):
    """ 爆炸效果 """
    def __init__(self, position, interval = None, images = None):
        global sprites

        self.position = [position[0]-16, position[1]-16]

        # False表示已爆炸完
        self.active = True

        if interval == None:
            interval = 100

        if images == None:
            images = [
                # 三種爆炸效果
                sprites.subsurface(0, 80*2, 32*2, 32*2),
                sprites.subsurface(32*2, 80*2, 32*2, 32*2),
                sprites.subsurface(64*2, 80*2, 32*2, 32*2),
            ]

        images.reverse()
        self.images = [] + images
        self.image = self.images.pop()

        gtimer.add(interval, lambda :self.update(), len(self.images) + 1)

    def draw(self):
        """ 畫爆炸效果 """
        global screen
        screen.blit(self.image, self.position)

    def update(self):
        if len(self.images) > 0:
            self.image = self.images.pop()
        else:
            self.active = False


class Level(object):
    """ 地形圖 """
    # 地形常量
    (TILE_EMPTY, TILE_BRICK, TILE_STEEL, TILE_WATER, TILE_GRASS, TILE_FROZE) = range(6)

    # 地形像素尺寸
    TILE_SIZE = 16

    def __init__(self, level_nr = None):
        global sprites

        # 限定地形圖上同时最多出現四個敵人
        self.max_active_enemies = 4

        tile_images = [
            pygame.Surface((8*2, 8*2)),
            sprites.subsurface(48*2, 64*2, 8*2, 8*2),
            sprites.subsurface(48*2, 72*2, 8*2, 8*2),
            sprites.subsurface(56*2, 72*2, 8*2, 8*2),
            sprites.subsurface(64*2, 64*2, 8*2, 8*2),
            sprites.subsurface(64*2, 64*2, 8*2, 8*2),
            sprites.subsurface(72*2, 64*2, 8*2, 8*2),
            sprites.subsurface(64*2, 72*2, 8*2, 8*2),
        ]
        self.tile_empty = tile_images[0]
        # 磚牆
        self.tile_brick = tile_images[1]
        # 鋼板
        self.tile_steel = tile_images[2]
        # 森林
        self.tile_grass = tile_images[3]
        # 海水
        self.tile_water = tile_images[4]
        self.tile_water1= tile_images[4]
        self.tile_water2= tile_images[5]
        # 地板
        self.tile_froze = tile_images[6]

        # 一共35關，如果大於35關則從第1关继续开始，如37表示第2关
        if level_nr == None:
            level_nr = 1
        else:
            level_nr = level_nr % 35

        if level_nr == 0:
            level_nr = 35

        # 加载對應等级的地形圖
        self.loadLevel(level_nr)
        # 包含所有可以被子弹消滅的地形的坐標和尺寸
        self.obstacle_rects = []
        self.updateObstacleRects()

        gtimer.add(400, lambda :self.toggleWaves())

    def hitTile(self, pos, power = 1, sound = False):
        """ 砲彈擊中地形的聲音及地形生命 """
        global play_sounds, sounds

        for tile in self.mapr:
            if tile[1].topleft == pos:
                # 砲彈擊中磚牆
                if tile[0] == self.TILE_BRICK:
                    if play_sounds and sound:
                        sounds["brick"].play()
                    self.mapr.remove(tile)
                    self.updateObstacleRects()
                    return True
                # 擊中鋼板
                elif tile[0] == self.TILE_STEEL:
                    if play_sounds and sound:
                        sounds["steel"].play()
                    if power == 2:
                        self.mapr.remove(tile)
                        self.updateObstacleRects()
                    return True
                else:
                    return False

    def toggleWaves(self):
        """ 切換海水圖片 """
        if self.tile_water == self.tile_water1:
            self.tile_water = self.tile_water2
        else:
            self.tile_water = self.tile_water1

    def loadLevel(self, level_nr = 1):
        """ 加载地形圖文件 """
        filename = "levels/"+str(level_nr)
        if (not os.path.isfile(filename)):
            return False
        level = []
        f = open(filename, "r")
        data = f.read().split("\n")
        self.mapr = []
        x, y = 0, 0
        for row in data:
            for ch in row:
                if ch == "#":
                    self.mapr.append((self.TILE_BRICK, pygame.Rect(x, y, self.TILE_SIZE, self.TILE_SIZE)))
                elif ch == "@":
                    self.mapr.append((self.TILE_STEEL, pygame.Rect(x, y, self.TILE_SIZE, self.TILE_SIZE)))
                elif ch == "~":
                    self.mapr.append((self.TILE_WATER, pygame.Rect(x, y, self.TILE_SIZE, self.TILE_SIZE)))
                elif ch == "%":
                    self.mapr.append((self.TILE_GRASS, pygame.Rect(x, y, self.TILE_SIZE, self.TILE_SIZE)))
                elif ch == "-":
                    self.mapr.append((self.TILE_FROZE, pygame.Rect(x, y, self.TILE_SIZE, self.TILE_SIZE)))
                x += self.TILE_SIZE
            x = 0
            y += self.TILE_SIZE
        return True

    def draw(self, tiles = None):
        """ 畫指定關卡的地形圖到遊戲窗口上 """
        global screen

        if tiles == None:
            tiles = [TILE_BRICK, TILE_STEEL, TILE_WATER, TILE_GRASS, TILE_FROZE]

        for tile in self.mapr:
            if tile[0] in tiles:
                if tile[0] == self.TILE_BRICK:
                    screen.blit(self.tile_brick, tile[1].topleft)
                elif tile[0] == self.TILE_STEEL:
                    screen.blit(self.tile_steel, tile[1].topleft)
                elif tile[0] == self.TILE_WATER:
                    screen.blit(self.tile_water, tile[1].topleft)
                elif tile[0] == self.TILE_FROZE:
                    screen.blit(self.tile_froze, tile[1].topleft)
                elif tile[0] == self.TILE_GRASS:
                    screen.blit(self.tile_grass, tile[1].topleft)

    def updateObstacleRects(self):
        """ 所有可以被子彈消滅的地形的座標和尺寸 """
        global castle
        self.obstacle_rects = [castle.rect]     # 玩家基地是可以被子弹消灭的

        for tile in self.mapr:
            if tile[0] in (self.TILE_BRICK, self.TILE_STEEL, self.TILE_WATER):
                self.obstacle_rects.append(tile[1])

    def buildFortress(self, tile):
        """ 圍繞玩家基地的磚牆 """
        positions = [
            (11*self.TILE_SIZE, 23*self.TILE_SIZE),
            (11*self.TILE_SIZE, 24*self.TILE_SIZE),
            (11*self.TILE_SIZE, 25*self.TILE_SIZE),
            (14*self.TILE_SIZE, 23*self.TILE_SIZE),
            (14*self.TILE_SIZE, 24*self.TILE_SIZE),
            (14*self.TILE_SIZE, 25*self.TILE_SIZE),
            (12*self.TILE_SIZE, 23*self.TILE_SIZE),
            (13*self.TILE_SIZE, 23*self.TILE_SIZE),
        ]

        obsolete = []

        for i, rect in enumerate(self.mapr):
            if rect[1].topleft in positions:
                obsolete.append(rect)
        for rect in obsolete:
            self.mapr.remove(rect)

        for pos in positions:
            self.mapr.append((tile, pygame.Rect(pos, [self.TILE_SIZE, self.TILE_SIZE])))

        self.updateObstacleRects()


class Tank(object):
    """ 坦克基類 """
    # 坦克方向
    (DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT) = range(4)
    # 坦克狀態
    (STATE_SPAWNING, STATE_DEAD, STATE_ALIVE, STATE_EXPLODING) = range(4)
    # 玩家坦克 or 敵人坦克
    (SIDE_PLAYER, SIDE_ENEMY) = range(2)

    def __init__(self, level, side, position = None, direction = None, filename = None):
        global sprites

        # 坦克生命值，生命值小於1表示被消滅
        self.health = 100

        # 坦克是否癱瘓(為True則不能移動但能轉向和開炮)
        self.paralised = False

        # 為True則坦克不能移動、轉向和開炮
        self.paused = False

        # 坦克是否是無敵狀態
        self.shielded = False

        # 移動速度，單位像素
        self.speed = 2

        # 坦克最多保持的active砲彈數
        self.max_active_bullets = 1

        # 坦克陣營
        self.side = side

        # 閃爍狀態，0關閉，1開啟
        self.flash = 0

        # 0表示普通坦克，1砲彈更快，2雙發砲彈，3砲彈可以消滅鋼板
        self.superpowers = 0

        # 為True則表示坦克被毁後會留下一個寶物
        self.bonus = None

        # 指定按鍵控制坦克的開火和向上、向右、向下、向左移動
        self.controls = [pygame.K_SPACE, pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT]

        # 是否按下四個方向的方向鍵
        self.pressed = [False] * 4

        # 坦克無敵時的狀態效果
        self.shield_images = [
            sprites.subsurface(0, 48*2, 16*2, 16*2),
            sprites.subsurface(16*2, 48*2, 16*2, 16*2),
        ]
        self.shield_image = self.shield_images[0]
        self.shield_index = 0

        # 出現新坦克時的顯示效果
        self.spawn_images = [
            sprites.subsurface(32*2, 48*2, 16*2, 16*2),
            sprites.subsurface(48*2, 48*2, 16*2, 16*2),
        ]
        self.spawn_image = self.spawn_images[0]
        self.spawn_index = 0

        self.level = level

        # 坦克出現的位置
        if position != None:
            self.rect = pygame.Rect(position, (26, 26))
        else:
            self.rect = pygame.Rect(0, 0, 26, 26)

        # 坦克出現時的方向
        if direction == None:
            self.direction = random.choice([self.DIR_RIGHT, self.DIR_DOWN, self.DIR_LEFT])
        else:
            self.direction = direction

        self.state = self.STATE_SPAWNING

        # 播放新坦克出現時的效果
        self.timer_uuid_spawn = gtimer.add(100, lambda :self.toggleSpawnImage())
        # 產生新坦克的效果出現1秒後终止，並出現坦克
        self.timer_uuid_spawn_end = gtimer.add(1000, lambda :self.endSpawning())

    def endSpawning(self):
        """ 停止播放新坦克出現效果，坦克出現，可以操作 """
        self.state = self.STATE_ALIVE
        gtimer.destroy(self.timer_uuid_spawn_end)


    def toggleSpawnImage(self):
        """ 產生新坦克時的效果 """
        if self.state != self.STATE_SPAWNING:
            gtimer.destroy(self.timer_uuid_spawn)
            return
        self.spawn_index += 1
        if self.spawn_index >= len(self.spawn_images):
            self.spawn_index = 0
        # 每回調該方法一次，切換一次圖像
        self.spawn_image = self.spawn_images[self.spawn_index]

    def toggleShieldImage(self):
        """ 用於坦克的無敵狀態顯示 """
        if self.state != self.STATE_ALIVE:
            gtimer.destroy(self.timer_uuid_shield)
            return
        if self.shielded:
            self.shield_index += 1
            if self.shield_index >= len(self.shield_images):
                self.shield_index = 0
            # 每回調該方法一次，切换一次圖像
            self.shield_image = self.shield_images[self.shield_index]

    def draw(self):
        """ 畫坦克 """
        global screen
        if self.state == self.STATE_ALIVE:
            screen.blit(self.image, self.rect.topleft)
            #pygame.image.load('assets/sprites/tankpic.jpeg').convert_alpha()
            if self.shielded:
                screen.blit(self.shield_image, [self.rect.left-3, self.rect.top-3])
        # 坦克爆炸
        elif self.state == self.STATE_EXPLODING:
            self.explosion.draw()
        # 產生新坦克
        elif self.state == self.STATE_SPAWNING:
            screen.blit(self.spawn_image, self.rect.topleft)

    def explode(self):
        """ 坦克爆炸 """
        if self.state != self.STATE_DEAD:
            self.state = self.STATE_EXPLODING
            self.explosion = Explosion(self.rect.topleft)

            if self.bonus:
                self.spawnBonus()   #坦克爆炸後出現爆炸

    def fire(self, forced = False):
        """
        發射子彈
        返回True表示已發射子彈，False為其他
        """
        global bullets, labels

        # 坦克被消滅，不再發射砲彈
        if self.state != self.STATE_ALIVE:
            gtimer.destroy(self.timer_uuid_fire)
            return False

        if self.paused:
            return False

        if not forced:
            # 同一輛坦克只能保持一定的active砲彈數
            # 遊戲窗口內最多屬於同一輛坦克的砲彈數
            active_bullets = 0
            for bullet in bullets:
                if bullet.owner_class == self and bullet.state == bullet.STATE_ACTIVE:
                    active_bullets += 1
            if active_bullets >= self.max_active_bullets:
                return False

        bullet = Bullet(self.level, self.rect.topleft, self.direction)

        if self.superpowers > 0:
            bullet.speed = 8

        if self.superpowers > 2:
            bullet.power = 2

        if self.side == self.SIDE_PLAYER:
            bullet.owner = self.SIDE_PLAYER
        else:
            bullet.owner = self.SIDE_ENEMY
            self.bullet_queued = False

        bullet.owner_class = self
        bullets.append(bullet)
        return True

    def rotate(self, direction, fix_position = True):
        """ 坦克轉向 """
        self.direction = direction

        # 加載對應方向的坦克圖像
        if direction == self.DIR_UP:
            self.image = self.image_up
        elif direction == self.DIR_RIGHT:
            self.image = self.image_right
        elif direction == self.DIR_DOWN:
            self.image = self.image_down
        elif direction == self.DIR_LEFT:
            self.image = self.image_left

        if fix_position:
            new_x = self.nearest(self.rect.left, 8) + 3
            new_y = self.nearest(self.rect.top, 8) + 3

            if (abs(self.rect.left - new_x) < 5):
                self.rect.left = new_x

            if (abs(self.rect.top - new_y) < 5):
                self.rect.top = new_y

    def turnAround(self):
        """ 坦克朝向相反方向 """
        if self.direction in (self.DIR_UP, self.DIR_RIGHT):
            self.rotate(self.direction + 2, False)
        else:
            self.rotate(self.direction - 2, False)

    def update(self, time_passed):
        if self.state == self.STATE_EXPLODING:
            if not self.explosion.active:
                self.state = self.STATE_DEAD
                del self.explosion

    def nearest(self, num, base):
        return int(round(num / (base * 1.0)) * base)


    def bulletImpact(self, friendly_fire = False, damage = 100, tank = None):
        """ 子彈碰撞規則，敵方坦克被敵方砲彈擊中不會爆炸 """
        global play_sounds, sounds

        # 坦克處於無敵狀態中
        if self.shielded:
            return True

        # 坦克被對方坦克砲彈擊中
        if not friendly_fire:
            self.health -= damage
            if self.health < 1:
                # 敵方坦克被擊中，計分
                if self.side == self.SIDE_ENEMY:
                    tank.trophies["enemy"+str(self.type)] += 1
                    points = (self.type+1) * 100
                    tank.score += points
                    if play_sounds:
                        sounds["explosion"].play()

                    labels.append(Label(self.rect.topleft, str(points), 500))

                # 坦克爆炸
                self.explode()
            return True

        # 敵方坦克被敵方砲彈擊中
        if self.side == self.SIDE_ENEMY:
            return False

        # 玩家坦克被玩家砲彈擊中，會進入癱瘓狀態
        elif self.side == self.SIDE_PLAYER:
            if not self.paralised:
                self.setParalised(True)
                self.timer_uuid_paralise = gtimer.add(10000, lambda :self.setParalised(False), 1)
            return True

    def setParalised(self, paralised = True):
        """ 坦克癱瘓狀態 """
        if self.state != self.STATE_ALIVE:
            gtimer.destroy(self.timer_uuid_paralise)
            return
        self.paralised = paralised


class Enemy(Tank):
    """ 敵方坦克 """
    # 四種類似的坦克
    (TYPE_BASIC, TYPE_FAST, TYPE_POWER, TYPE_ARMOR) = range(4)

    def __init__(self, level, type, position = None, direction = None, filename = None):
        Tank.__init__(self, level, type, position = None, direction = None, filename = None)

        global enemies, sprites

        # 為True則不開火
        self.bullet_queued = False

        # 隨機出現坦克類型
        if len(level.enemies_left) > 0:
            self.type = level.enemies_left.pop()
        else:
            self.state = self.STATE_DEAD
            return

        if self.type == self.TYPE_BASIC:
            self.speed = 1
        elif self.type == self.TYPE_FAST:
            self.speed = 3
        elif self.type == self.TYPE_POWER:
            self.superpowers = 1
        elif self.type == self.TYPE_ARMOR:
            self.health = 400

        # 敵方坦克爆炸後有五分之一機會留下一個寶物
        # 且場上同時只能有一個寶物
        if random.randint(1, 5) == 1:
            self.bonus = True
            for enemy in enemies:
                if enemy.bonus:
                    self.bonus = False
                    break

        images = [
            sprites.subsurface(32*2, 0, 13*2, 15*2),
            sprites.subsurface(48*2, 0, 13*2, 15*2),
            sprites.subsurface(64*2, 0, 13*2, 15*2),
            sprites.subsurface(80*2, 0, 13*2, 15*2),
            sprites.subsurface(32*2, 16*2, 13*2, 15*2),
            sprites.subsurface(48*2, 16*2, 13*2, 15*2),
            sprites.subsurface(64*2, 16*2, 13*2, 15*2),
            sprites.subsurface(80*2, 16*2, 13*2, 15*2)
        ]

        self.image = images[self.type+0]

        self.image_up = self.image;
        self.image_left = pygame.transform.rotate(self.image, 90)
        self.image_down = pygame.transform.rotate(self.image, 180)
        self.image_right = pygame.transform.rotate(self.image, 270)

        if self.bonus:
            self.image1_up = self.image_up;
            self.image1_left = self.image_left
            self.image1_down = self.image_down
            self.image1_right = self.image_right

            self.image2 = images[self.type+4]
            self.image2_up = self.image2;
            self.image2_left = pygame.transform.rotate(self.image2, 90)
            self.image2_down = pygame.transform.rotate(self.image2, 180)
            self.image2_right = pygame.transform.rotate(self.image2, 270)

        self.rotate(self.direction, False)

        # 敵方坦克出現位置
        if position == None:
            self.rect.topleft = self.getFreeSpawningPosition()
            if not self.rect.topleft:
                self.state = self.STATE_DEAD
                return

        # 計算坦克自動移動路徑
        self.path = self.generatePath(self.direction)

        # 每秒發射一顆子彈
        self.timer_uuid_fire = gtimer.add(1000, lambda :self.fire())

        # 寶物閃爍
        if self.bonus:
            self.timer_uuid_flash = gtimer.add(200, lambda :self.toggleFlash())

    def toggleFlash(self):
        """ 切換閃爍狀態 """
        if self.state not in (self.STATE_ALIVE, self.STATE_SPAWNING):
            gtimer.destroy(self.timer_uuid_flash)
            return
        self.flash = not self.flash
        if self.flash:
            self.image_up = self.image2_up
            self.image_right = self.image2_right
            self.image_down = self.image2_down
            self.image_left = self.image2_left
        else:
            self.image_up = self.image1_up
            self.image_right = self.image1_right
            self.image_down = self.image1_down
            self.image_left = self.image1_left
        self.rotate(self.direction, False)

    def spawnBonus(self):
        """ 產生新的寶物 """

        global bonuses

        if len(bonuses) > 0:
            return
        bonus = Bonus(self.level)
        bonuses.append(bonus)
        gtimer.add(500, lambda :bonus.toggleVisibility())
        gtimer.add(10000, lambda :bonuses.remove(bonus), 1)


    def getFreeSpawningPosition(self):
        global players, enemies

        available_positions = [
            [(self.level.TILE_SIZE * 2 - self.rect.width) / 2, (self.level.TILE_SIZE * 2 - self.rect.height) / 2],
            [12 * self.level.TILE_SIZE + (self.level.TILE_SIZE * 2 - self.rect.width) / 2, (self.level.TILE_SIZE * 2 - self.rect.height) / 2],
            [24 * self.level.TILE_SIZE + (self.level.TILE_SIZE * 2 - self.rect.width) / 2,  (self.level.TILE_SIZE * 2 - self.rect.height) / 2]
        ]

        random.shuffle(available_positions)

        # 隨機挑選一個沒被其他物體佔用的坐標出現新坦克
        for pos in available_positions:
            enemy_rect = pygame.Rect(pos, [26, 26])

            collision = False
            for enemy in enemies:
                if enemy_rect.colliderect(enemy.rect):
                    collision = True
                    continue

            if collision:
                continue

            collision = False
            for player in players:
                if enemy_rect.colliderect(player.rect):
                    collision = True
                    continue

            if collision:
                continue

            return pos
        return False

    def move(self):
        """ 敵方坦克移動 """
        global players, enemies, bonuses

        if self.state != self.STATE_ALIVE or self.paused or self.paralised:
            return

        # 生成自動移動路徑
        if self.path == []:
            self.path = self.generatePath(None, True)

        new_position = self.path.pop(0)

        # 坦克下一個出現位置超出遊戲界面，則重新計算自動移動路徑
        if self.direction == self.DIR_UP:
            if new_position[1] < 0:
                self.path = self.generatePath(self.direction, True)
                return
        elif self.direction == self.DIR_RIGHT:
            if new_position[0] > (416 - 26):
                self.path = self.generatePath(self.direction, True)
                return
        elif self.direction == self.DIR_DOWN:
            if new_position[1] > (416 - 26):
                self.path = self.generatePath(self.direction, True)
                return
        elif self.direction == self.DIR_LEFT:
            if new_position[0] < 0:
                self.path = self.generatePath(self.direction, True)
                return

        new_rect = pygame.Rect(new_position, [26, 26])

        # 撞上地形，重新計算坦克自動移動路徑
        if new_rect.collidelist(self.level.obstacle_rects) != -1:
            self.path = self.generatePath(self.direction, True)
            return

        # 撞上其他敵方坦克，坦克轉向反方向，並重新計算坦克自動移動路徑
        for enemy in enemies:
            if enemy != self and new_rect.colliderect(enemy.rect):
                self.turnAround()
                self.path = self.generatePath(self.direction)
                return

        # 撞上玩家坦克，坦克轉向反方向，並重新計算坦克自動移動路徑
        for player in players:
            if new_rect.colliderect(player.rect):
                self.turnAround()
                self.path = self.generatePath(self.direction)
                return

        # 撞上寶物，寶物消失，敵人坦克不會獲得任何增益效果
        for bonus in bonuses:
            if new_rect.colliderect(bonus.rect):
                bonuses.remove(bonus)

        # 沒撞上任何東西，則將坐標設置為坦克移動的下一個坐標
        self.rect.topleft = new_rect.topleft


    def update(self, time_passed):
        Tank.update(self, time_passed)
        if self.state == self.STATE_ALIVE and not self.paused:
            self.move()

    def generatePath(self, direction = None, fix_direction = False):
        """
        敵方坦克自動移動規則：
        先沿著坦克指向方向走，不通則隨機選擇一個方向
        """
        all_directions = [self.DIR_UP, self.DIR_RIGHT, self.DIR_DOWN, self.DIR_LEFT]

        if direction == None:
            if self.direction in [self.DIR_UP, self.DIR_RIGHT]:
                opposite_direction = self.direction + 2
            else:
                opposite_direction = self.direction - 2
            directions = all_directions
            # 打亂方向順序
            random.shuffle(directions)
            # 將坦克方向的相反方向放到最後，最後才選擇反方向移動
            directions.remove(opposite_direction)
            directions.append(opposite_direction)
        else:
            if direction in [self.DIR_UP, self.DIR_RIGHT]:
                opposite_direction = direction + 2
            else:
                opposite_direction = direction - 2
            directions = all_directions
            random.shuffle(directions)
            directions.remove(opposite_direction)
            directions.remove(direction)
            # 優先選擇坦克方向移動
            directions.insert(0, direction)
            # 最後選擇坦克方向相反方向移動
            directions.append(opposite_direction)

        x = int(round(self.rect.left / 16))
        y = int(round(self.rect.top / 16))

        new_direction = None

        # 朝首選的指定方向移動8像素，如果超出遊戲界面，則轉向反方向
        # 如果與地形障礙物碰撞，轉為其他方向繼續嘗試
        for direction in directions:
            if direction == self.DIR_UP and y > 1:
                new_pos_rect = self.rect.move(0, -8)
                if new_pos_rect.collidelist(self.level.obstacle_rects) == -1:
                    new_direction = direction
                    break
            elif direction == self.DIR_RIGHT and x < 24:
                new_pos_rect = self.rect.move(8, 0)
                if new_pos_rect.collidelist(self.level.obstacle_rects) == -1:
                    new_direction = direction
                    break
            elif direction == self.DIR_DOWN and y < 24:
                new_pos_rect = self.rect.move(0, 8)
                if new_pos_rect.collidelist(self.level.obstacle_rects) == -1:
                    new_direction = direction
                    break
            elif direction == self.DIR_LEFT and x > 1:
                new_pos_rect = self.rect.move(-8, 0)
                if new_pos_rect.collidelist(self.level.obstacle_rects) == -1:
                    new_direction = direction
                    break

        #  超出遊戲界面，轉為反方向
        if new_direction == None:
            new_direction = opposite_direction

        # 如果坦克繼續沿著坦克當前方向移動，則無須修正坐標
        if fix_direction and new_direction == self.direction:
            fix_direction = False

        # 坦克轉向並修正轉向後的坐標
        self.rotate(new_direction, fix_direction)

        positions = []

        x = self.rect.left
        y = self.rect.top

        if new_direction in (self.DIR_RIGHT, self.DIR_LEFT):
            axis_fix = self.nearest(y, 16) - y
        else:
            axis_fix = self.nearest(x, 16) - x
        axis_fix = 0

        pixels = self.nearest(random.randint(1, 12) * 32, 32) + axis_fix + 3

        # 計算自動移動路徑
        if new_direction == self.DIR_UP:
            for px in range(0, pixels, self.speed):
                positions.append([x, y-px])
        elif new_direction == self.DIR_RIGHT:
            for px in range(0, pixels, self.speed):
                positions.append([x+px, y])
        elif new_direction == self.DIR_DOWN:
            for px in range(0, pixels, self.speed):
                positions.append([x, y+px])
        elif new_direction == self.DIR_LEFT:
            for px in range(0, pixels, self.speed):
                positions.append([x-px, y])

        return positions


class Player(Tank):
    """ 玩家坦克 """
    def __init__(self, level, type, position = None, direction = None, filename = None):
        Tank.__init__(self, level, type, position = None, direction = None, filename = None)
        global sprites

        if filename == None:
            filename = (0, 0, 16*2, 16*2)
        # 出現位置和方向
        self.start_position = position
        self.start_direction = direction
        # 生命
        self.lives = 3

        # 得分
        self.score = 0

        # 收集寶物數量和消滅敵方坦克數量
        self.trophies = {
            "bonus" : 0,
            "enemy0" : 0,
            "enemy1" : 0,
            "enemy2" : 0,
            "enemy3" : 0
        }

        # 玩家坦克圖像
        self.image = sprites.subsurface(filename)
        self.image_up = self.image
        self.image_left = pygame.transform.rotate(self.image, 90)
        self.image_down = pygame.transform.rotate(self.image, 180)
        self.image_right = pygame.transform.rotate(self.image, 270)

        # 玩家坦克方向默認向上
        if direction == None:
            self.rotate(self.DIR_UP, False)
        else:
            self.rotate(direction, False)

    def move(self, direction):
        """ 玩家坦克移動 """
        global players, enemies, bonuses

        if self.state == self.STATE_EXPLODING:
            if not self.explosion.active:
                self.state = self.STATE_DEAD
                del self.explosion

        if self.state != self.STATE_ALIVE:
            return

        # 坦克轉向
        if self.direction != direction:
            self.rotate(direction)

        if self.paralised:
            return

        # 計算坦克出現的新位置，不能超出遊戲窗口範圍
        if direction == self.DIR_UP:
            new_position = [self.rect.left, self.rect.top - self.speed]
            if new_position[1] < 0:
                return
        elif direction == self.DIR_RIGHT:
            new_position = [self.rect.left + self.speed, self.rect.top]
            if new_position[0] > (416 - 26):
                return
        elif direction == self.DIR_DOWN:
            new_position = [self.rect.left, self.rect.top + self.speed]
            if new_position[1] > (416 - 26):
                return
        elif direction == self.DIR_LEFT:
            new_position = [self.rect.left - self.speed, self.rect.top]
            if new_position[0] < 0:
                return

        player_rect = pygame.Rect(new_position, [26, 26])

        # 撞上地形
        if player_rect.collidelist(self.level.obstacle_rects) != -1:
            return

        # 撞上其它玩家坦克
        for player in players:
            if player != self and player.state == player.STATE_ALIVE and player_rect.colliderect(player.rect) == True:
                return

        # 撞上敵方坦克
        for enemy in enemies:
            if player_rect.colliderect(enemy.rect) == True:
                return

        # 撞上寶物
        for bonus in bonuses:
            if player_rect.colliderect(bonus.rect) == True:
                self.bonus = bonus

        # 更新玩家坦克出現的新坐標（沒撞上任何阻擋物和沒超出遊戲窗口）
        self.rect.topleft = (new_position[0], new_position[1])

    def reset(self):
        """ 重新初始化玩家坦克狀態 """
        self.rotate(self.start_direction, False)
        self.rect.topleft = self.start_position
        self.superpowers = 1                    #子彈射速#子彈強度
        self.max_active_bullets = 10            #玩家坦克子彈射速
        self.health = 100                      #坦克血量
        self.paralised = False
        self.paused = False
        self.pressed = [False] * 4
        self.state = self.STATE_ALIVE


class Game(object):
    # 方向
    (DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT) = range(4)
    TILE_SIZE = 16

    def __init__(self):
        global screen, sprites, play_sounds, sounds
        # 遊戲窗口位於屏幕中央
        os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'

        if play_sounds:
            # 預設mixer初始化參數，必須位於pygame.init()之前
            pygame.mixer.pre_init(44100, -16, 1, 512)

        pygame.init()
        size = width, height = 480, 416
        # 創建遊戲窗口
        screen = pygame.display.set_mode(size)
        # 遊戲窗口的文字標題
        pygame.display.set_caption("坦克大战")
        # 用於設置幀數
        self.clock = pygame.time.Clock()

        # 遊戲中所有圖片資源都在這裡了
        sprites = pygame.transform.scale(pygame.image.load("images/sprites.gif"), [192, 224])

        # 設置遊戲窗口的圖形標題，默認為pygame官方圖標
        pygame.display.set_icon(sprites.subsurface(0, 0, 13*2, 13*2))

        if play_sounds:
            pygame.mixer.init(44100, -16, 1, 514)
            # 加載聲音文件
            sounds["start"] = pygame.mixer.Sound("sounds/gamestart.ogg")
            sounds["endnew"] = pygame.mixer.Sound("sounds/gameovernew.ogg")
            sounds["score"] = pygame.mixer.Sound("sounds/score.ogg")
            sounds["bg"] = pygame.mixer.Sound("sounds/background.ogg")
            sounds["fire"] = pygame.mixer.Sound("sounds/fire.ogg")
            sounds["bonus"] = pygame.mixer.Sound("sounds/bonus.ogg")
            sounds["explosion"] = pygame.mixer.Sound("sounds/explosion.ogg")
            sounds["brick"] = pygame.mixer.Sound("sounds/brick.ogg")
            sounds["steel"] = pygame.mixer.Sound("sounds/steel.ogg")
            sounds["back"] = pygame.mixer.Sound("sounds/back.ogg")
            sounds["diemuc"] = pygame.mixer.Sound("sounds/diemuc.ogg")
            
        # 表示還有多少個敵人
        self.enemy_life_image = sprites.subsurface(81*2, 57*2, 7*2, 7*2)
        # 表示自己還有多少條生命
        self.player_life_image = sprites.subsurface(89*2, 56*2, 7*2, 8*2)
        # 表示第幾關
        self.flag_image = sprites.subsurface(64*2, 49*2, 16*2, 15*2)

        # 用在選擇界面，選擇單人模式還是雙人模式
        self.player_image = pygame.transform.rotate(sprites.subsurface(0, 0, 13*2, 13*2), 270)

        self.timefreeze = False

        # 加載自定義字體，字體大小為16
        #self.font = pygame.font.Font("fonts/prstart.ttf", 16)
        self.font = pygame.font.Font("fonts/heiti.ttf", 16)

        # 遊戲結束畫面
        self.im_game_over = pygame.Surface((64, 40))
        self.im_game_over.set_colorkey((0,0,0))
        self.im_game_over.blit(self.font.render("Game", False, (127, 64, 64)), [0, 0])
        self.im_game_over.blit(self.font.render("OVER", False, (127, 64, 64)), [0, 20])
        self.game_over_y = 416+40

        # 默認為單人遊戲
        self.nr_of_players = 1

        # 初始化遊戲環境
        del players[:]
        del bullets[:]
        del enemies[:]
        del bonuses[:]

    def triggerBonus(self, bonus, player):
        """ 觸發寶物效果 """

        global enemies, labels, play_sounds, sounds

        if play_sounds:
            sounds["bonus"].play()

        # 玩家坦克吃寶物數量
        player.trophies["bonus"] += 1
        player.score += 500

        # 手雷寶物效果
        if bonus.bonus == bonus.BONUS_GRENADE:
            for enemy in enemies:
                enemy.explode()
        # 頭盔寶物效果
        elif bonus.bonus == bonus.BONUS_HELMET:
            self.shieldPlayer(player, True, 10000)
        # 鐵寶物效果
        elif bonus.bonus == bonus.BONUS_SHOVEL:
            self.level.buildFortress(self.level.TILE_STEEL)
            gtimer.add(10000, lambda :self.level.buildFortress(self.level.TILE_BRICK), 1)
        # 星星寶物效果
        elif bonus.bonus == bonus.BONUS_STAR:
            player.speed = player.speed + 1
            if player.speed >= 5:
                player.speed = 5
        # 肌肉寶物效果
        elif bonus.bonus == bonus.BONUS_TANK:
            player.lives += 1
            player.health = player.health + 50
        # 時鐘寶物效果
        elif bonus.bonus == bonus.BONUS_TIMER:
            self.toggleEnemyFreeze(True)
            gtimer.add(10000, lambda :self.toggleEnemyFreeze(False), 1)
        bonuses.remove(bonus)
        

        labels.append(Label(bonus.rect.topleft, "500", 500))

    def shieldPlayer(self, player, shield = True, duration = None):
        """
        玩家坦克剛出現時有短暂的無敵狀態
        該方法用於添加/移除玩家的無敵狀態
        """
        player.shielded = shield
        if shield:
            player.timer_uuid_shield = gtimer.add(100, lambda :player.toggleShieldImage())
        else:
            gtimer.destroy(player.timer_uuid_shield)

        if shield and duration != None:
            gtimer.add(duration, lambda :self.shieldPlayer(player, False), 1)


    def spawnEnemy(self):
        """ 產生敵方坦克 """
        global enemies

        if len(enemies) >= self.level.max_active_enemies:
            return
        if len(self.level.enemies_left) < 1 or self.timefreeze:
            return
        enemy = Enemy(self.level, 1)

        enemies.append(enemy)


    def respawnPlayer(self, player, clear_scores = False):
        # 初始化玩家坦克属性
        player.reset()

        # 清除玩家所有得分
        if clear_scores:
            player.trophies = {
                "bonus" : 0, "enemy0" : 0, "enemy1" : 0, "enemy2" : 0, "enemy3" : 0
            }

        # 玩家坦克出現時的無敵效果顯示，默認4秒無敵
        self.shieldPlayer(player, True, 4000)

    def gameOver(self):
        """ 遊戲结束 """
        global play_sounds, sounds

        print ("Game Over")
        if play_sounds:
            for sound in sounds:
                sounds[sound].stop()
            sounds["endnew"].play()

        self.game_over_y = 416+40

        self.game_over = True
        gtimer.add(3000, lambda :self.showScores(), 1)

    def gameOverScreen(self):
        """ 顯示遊戲结束界面 """
        global screen

        # 结束遊戲主循環
        self.running = False

        screen.fill([0, 0, 0])

        self.writeInBricks("game", [125, 140])
        self.writeInBricks("over", [125, 220])
        pygame.display.flip()

        while 1:
            time_passed = self.clock.tick(50)
            for event in pygame.event.get():
                # 按關閉按鈕退出游戏
                if event.type == pygame.QUIT:
                    quit()
                elif event.type == pygame.KEYDOWN:
                    # 按回車顯示選擇界面
                    if event.key == pygame.K_RETURN:
                        self.showMenu()
                        return

    def showMenu(self):
        """ 選擇界面，接收用戶的選擇並進入下一關 """
        global players, screen

        self.running = False
        del gtimer.timers[:]
        # 0關就是選擇界面
        self.stage = 0

        # 把選擇界面畫到遊戲窗口中
        self.animateIntroScreen()

        main_loop = True
        while main_loop:
            # 每秒50幀
            time_passed = self.clock.tick(50)

            for event in pygame.event.get():
                # 點擊關閉按鈕，退出遊戲
                if event.type == pygame.QUIT:
                    quit()
                # 選擇單人模式還是雙人模式的邏輯
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        # 按了方向鍵向上鍵，如果之前是指向雙人模式，則需要重畫選擇畫面，以便指向單人模式
                        if self.nr_of_players == 2:
                            self.nr_of_players = 1
                            self.drawIntroScreen()
                    elif event.key == pygame.K_DOWN:
                        if self.nr_of_players == 1:
                            self.nr_of_players = 2
                            self.drawIntroScreen()
                    elif event.key == pygame.K_RETURN:      # 按回車鍵，結束選擇
                        main_loop = False

        del players[:]
        self.nextLevel()

    def reloadPlayers(self):
        """ 初始化玩家坦克 """
        global players

        if len(players) == 0:
            # 玩家一
            x = 8 * self.TILE_SIZE + (self.TILE_SIZE * 2 - 26) / 2
            y = 24 * self.TILE_SIZE + (self.TILE_SIZE * 2 - 26) / 2

            player = Player(
                self.level, 0, [x, y], self.DIR_UP, (0, 0, 13*2, 13*2)
            )
            players.append(player)

            # 玩家二
            if self.nr_of_players == 2:
                x = 16 * self.TILE_SIZE + (self.TILE_SIZE * 2 - 26) / 2
                y = 24 * self.TILE_SIZE + (self.TILE_SIZE * 2 - 26) / 2
                player = Player(
                    self.level, 0, [x, y], self.DIR_UP, (16*2, 0, 13*2, 13*2)
                )
                player.controls = [102, 119, 100, 115, 97]
                players.append(player)

        for player in players:
            player.level = self.level
            self.respawnPlayer(player, True)

    def showScores(self):
        """ 計分頁面 """
        global screen, sprites, players, play_sounds, sounds

        # 終止遊戲主循環
        self.running = False

        # 清除所有計時器
        del gtimer.timers[:]

        # 停止播放所有的遊戲聲音
        if play_sounds:
            for sound in sounds:
                sounds[sound].stop()

        # 加載歷史遊戲得分
        hiscore = self.loadHiscore()

        if players[0].score > hiscore:
            hiscore = players[0].score
            self.saveHiscore(hiscore)
        if self.nr_of_players == 2 and players[1].score > hiscore:
            hiscore = players[1].score
            self.saveHiscore(hiscore)

        img_tanks = [
            sprites.subsurface(32*2, 0, 13*2, 15*2),
            sprites.subsurface(48*2, 0, 13*2, 15*2),
            sprites.subsurface(64*2, 0, 13*2, 15*2),
            sprites.subsurface(80*2, 0, 13*2, 15*2)
        ]

        img_arrows = [
            sprites.subsurface(81*2, 48*2, 7*2, 7*2),
            sprites.subsurface(88*2, 48*2, 7*2, 7*2)
        ]

        # 把遊戲窗口填充為黑色，方便後面顯示
        screen.fill([0, 0, 0])

        # 颜色
        black = pygame.Color("black")
        white = pygame.Color("white")
        purple = pygame.Color(127, 64, 64)
        pink = pygame.Color(191, 160, 128)

        screen.blit(self.font.render(u"最高得分", False, purple), [105, 35])
        screen.blit(self.font.render(str(hiscore), False, pink), [295, 35])

        screen.blit(self.font.render(u"關卡"+str(self.stage).rjust(3), False, white), [170, 65])

        screen.blit(self.font.render(u"玩家一", False, purple), [25, 95])

        #玩家1得分
        screen.blit(self.font.render(str(players[0].score).rjust(8), False, pink), [25, 125])

        if self.nr_of_players == 2:
            screen.blit(self.font.render(u"玩家二", False, purple), [320, 95])

            #玩家2得分
            screen.blit(self.font.render(str(players[1].score).rjust(8), False, pink), [325, 125])

        # 畫坦克圖像
        for i in range(4):
            screen.blit(img_tanks[i], [226, 160+(i*45)])
            screen.blit(img_arrows[0], [206, 168+(i*45)])
            if self.nr_of_players == 2:
                screen.blit(img_arrows[1], [258, 168+(i*45)])
        

        screen.blit(self.font.render("TOTAL", False, white), [70, 335])

        pygame.draw.line(screen, white, [170, 330], [307, 330], 4)

        pygame.display.flip()

        self.clock.tick(2)

        interval = 5

        # 開始計分，顯示玩家消滅坦克數和相關得分
        for i in range(4):

            tanks = players[0].trophies["enemy"+str(i)]

            for n in range(tanks+1):
                if n > 0 and play_sounds:
                    sounds["score"].play()

                screen.blit(self.font.render(str(n-1).rjust(2), False, black), [170, 168+(i*45)])
                screen.blit(self.font.render(str(n).rjust(2), False, white), [170, 168+(i*45)])
                screen.blit(self.font.render(str((n-1) * (i+1) * 100).rjust(4)+" PTS", False, black), [25, 168+(i*45)])
                screen.blit(self.font.render(str(n * (i+1) * 100).rjust(4)+" PTS", False, white), [25, 168+(i*45)])
                pygame.display.flip()
                self.clock.tick(interval)

            if self.nr_of_players == 2:
                tanks = players[1].trophies["enemy"+str(i)]

                for n in range(tanks+1):

                    if n > 0 and play_sounds:
                        sounds["score"].play()

                    screen.blit(self.font.render(str(n-1).rjust(2), False, black), [277, 168+(i*45)])
                    screen.blit(self.font.render(str(n).rjust(2), False, white), [277, 168+(i*45)])

                    screen.blit(self.font.render(str((n-1) * (i+1) * 100).rjust(4)+" PTS", False, black), [325, 168+(i*45)])
                    screen.blit(self.font.render(str(n * (i+1) * 100).rjust(4)+" PTS", False, white), [325, 168+(i*45)])

                    pygame.display.flip()
                    self.clock.tick(interval)

            self.clock.tick(interval)

        tanks = sum([i for i in players[0].trophies.values()]) - players[0].trophies["bonus"]
        screen.blit(self.font.render(str(tanks).rjust(2), False, white), [170, 335])
        if self.nr_of_players == 2:
            tanks = sum([i for i in players[1].trophies.values()]) - players[1].trophies["bonus"]
            screen.blit(self.font.render(str(tanks).rjust(2), False, white), [277, 335])

        pygame.display.flip()

        # 在積分頁面停留2秒
        self.clock.tick(1)
        self.clock.tick(1)

        if self.game_over:
            self.gameOverScreen()       #结束界面
        else:
            self.nextLevel()


    def draw(self):
        global screen, castle, players, enemies, bullets, bonuses
        # 先填充為黑色
        screen.fill([0, 0, 0])
        # 畫地形圖
        self.level.draw([self.level.TILE_EMPTY, self.level.TILE_BRICK, \
                        self.level.TILE_STEEL, self.level.TILE_FROZE, \
                        self.level.TILE_WATER])
        # 畫玩家基地
        castle.draw()

        for enemy in enemies:
            enemy.draw()

        for label in labels:
            label.draw()

        for player in players:
            player.draw()

        for bullet in bullets:
            bullet.draw()

        for bonus in bonuses:
            bonus.draw()

        self.level.draw([self.level.TILE_GRASS])

        # 遊戲結束了的話，顯示"game over"，從基地位置移到屏幕中間，每幀移動4像素
        if self.game_over:
            if self.game_over_y > 188:
                self.game_over_y -= 4
            screen.blit(self.im_game_over, [176, self.game_over_y]) # 176=(416-64)/2

        # 畫側邊欄，顯示敵人生命，玩家生命
        self.drawSidebar()

        pygame.display.flip()

    def drawSidebar(self):
        """ 畫側邊欄 """
        global screen, players, enemies

        x = 416
        y = 0
        screen.fill([100, 100, 100], pygame.Rect([416, 0], [64, 416]))

        xpos = x + 16
        ypos = y + 16

        # 畫敵人生命
        for n in range(len(self.level.enemies_left) + len(enemies)):
            screen.blit(self.enemy_life_image, [xpos, ypos])
            if n % 2 == 1:
                xpos = x + 16
                ypos+= 17
            else:
                xpos += 17

        # 畫玩家生命
        if pygame.font.get_init():
            text_color = pygame.Color('black')
            for n in range(len(players)):
                if n == 0:
                    screen.blit(self.font.render(str(n+1)+"P", False, text_color), [x+16, y+200])
                    screen.blit(self.font.render(str(players[n].lives), False, text_color), [x+31, y+215])
                    screen.blit(self.player_life_image, [x+17, y+215])
                else:
                    screen.blit(self.font.render(str(n+1)+"P", False, text_color), [x+16, y+240])
                    screen.blit(self.font.render(str(players[n].lives), False, text_color), [x+31, y+255])
                    screen.blit(self.player_life_image, [x+17, y+255])

            screen.blit(self.flag_image, [x+17, y+280])
            screen.blit(self.font.render(str(self.stage), False, text_color), [x+17, y+312])

    def drawIntroScreen(self, put_on_surface = True):
        """ 畫選擇界面 """
        global screen
        # 遊戲窗口圖片
        BACK_IMAGE = "./picture/back.jpeg"
        back_image = pygame.image.load(BACK_IMAGE)
        screen.blit(back_image, (0,0))
        
        self.writeInBricks("battle", [65, 80])
        self.writeInBricks("city", [129, 160])

        if pygame.font.get_init():
            # 之前獲得的最高得分
            hiscore = self.loadHiscore()
            # 選擇界面的内容
            screen.blit(self.font.render(u"最高得分-"+str(hiscore), True, pygame.Color('white')), [170, 35])
            screen.blit(self.font.render("1 PLAYER", True, pygame.Color('white')), [165, 250])
            screen.blit(self.font.render("2 PLAYERS", True, pygame.Color('white')), [165, 275])
            screen.blit(self.font.render("(c) 1980 1985 NAMCO LTD.", True, pygame.Color('white')), [140, 350])
            screen.blit(self.font.render("ALL RIGHTS RESERVED", True, pygame.Color('white')), [140, 380])

        # 畫self.player image圖像到選擇界面,接收按鍵事件來選擇單人或多人模式
        if self.nr_of_players == 1:
            screen.blit(self.player_image, [125, 245])
        elif self.nr_of_players == 2:
            screen.blit(self.player_image, [125, 270])

        # 是否立即畫選擇界面到遊戲窗口中
        if put_on_surface:
            pygame.display.flip()

    def animateIntroScreen(self):
        """ 選擇菜單從下往上滑動效果 """
        global screen
        # 畫選擇界面
        self.drawIntroScreen(False)
        # 獲取一個screen的拷貝，用於保存選擇界面，原界面填充回全黑
        screen_cp = screen.copy()
        screen.fill([0, 0, 0])

        # 畫選擇界面的y坐標，416表示從遊戲窗口最底部開始畫，0是最頂部
        y = 416
        while (y > 0):
            time_passed = self.clock.tick(50)
            # 在選擇界面從下往上滑動的過程中按回車鍵，則選擇界面立即填滿遊戲窗口
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        y = 0
                        break
            # 畫選擇界面到遊戲窗口中
            screen.blit(screen_cp, [0, y])
            pygame.display.flip()
            # 選擇界面每次上移5像素
            y -= 5

        # 最後把選擇界面完全填充到遊戲窗口中
        screen.blit(screen_cp, [0, 0])
        pygame.display.flip()


    def chunks(self, l, n):
        """ 將字符串分割成塊，n是每塊大小 """
        return [l[i:i+n] for i in range(0, len(l), n)]

    def writeInBricks(self, text, pos):
        global screen, sprites

        bricks = sprites.subsurface(56*2, 64*2, 8*2, 8*2)
        brick1 = bricks.subsurface((0, 0, 8, 8))
        brick2 = bricks.subsurface((8, 0, 8, 8))
        brick3 = bricks.subsurface((8, 8, 8, 8))
        brick4 = bricks.subsurface((0, 8, 8, 8))

        alphabet = {
            "a" : "0071b63c7ff1e3",
            "b" : "01fb1e3fd8f1fe",
            "c" : "00799e0c18199e",
            "e" : "01fb060f98307e",
            "g" : "007d860cf8d99f",
            "i" : "01f8c183060c7e",
            "l" : "0183060c18307e",
            "m" : "018fbffffaf1e3",
            "o" : "00fb1e3c78f1be",
            "r" : "01fb1e3cff3767",
            "t" : "01f8c183060c18",
            "v" : "018f1e3eef8e08",
            "y" : "019b3667860c18"
        }

        abs_x, abs_y = pos

        for letter in text.lower():

            binstr = ""
            for h in self.chunks(alphabet[letter], 2):
                binstr += str(bin(int(h, 16)))[2:].rjust(8, "0")
            binstr = binstr[7:]

            x, y = 0, 0
            letter_w = 0
            surf_letter = pygame.Surface((56, 56))
            for j, row in enumerate(self.chunks(binstr, 7)):
                for i, bit in enumerate(row):
                    if bit == "1":
                        if i%2 == 0 and j%2 == 0:
                            surf_letter.blit(brick1, [x, y])
                        elif i%2 == 1 and j%2 == 0:
                            surf_letter.blit(brick2, [x, y])
                        elif i%2 == 1 and j%2 == 1:
                            surf_letter.blit(brick3, [x, y])
                        elif i%2 == 0 and j%2 == 1:
                            surf_letter.blit(brick4, [x, y])
                        if x > letter_w:
                            letter_w = x
                    x += 8
                x = 0
                y += 8
            screen.blit(surf_letter, [abs_x, abs_y])
            abs_x += letter_w + 16

    def toggleEnemyFreeze(self, freeze = True):
        """ 寶物效果，暫停所有敵人 """
        global enemies

        for enemy in enemies:
            enemy.paused = freeze
        self.timefreeze = freeze


    def loadHiscore(self):
        """ 加載遊戲得分 """
        filename = ".hiscore"
        # 從文件中加載最高分數，沒有則直接返回20000
        if (not os.path.isfile(filename)):
            return 20000

        f = open(filename, "r")
        hiscore = int(f.read().strip())

        if hiscore > 19999 and hiscore < 1000000:
            return hiscore
        else:
            print ("cheater =[")
            return 20000

    def saveHiscore(self, hiscore):
        """ 保存遊戲得分 """
        try:
            f = open(".hiscore", "w")
            f.write(str(hiscore))
        except:
            print ("Can't save hiscore")
            return False
        finally:
            f.close()
        return True


    def finishLevel(self):
        """ 通過這一關，進入下一關 """

        global play_sounds, sounds

        if play_sounds:
            sounds["bg"].stop()

        self.active = False
        gtimer.add(3000, lambda :self.showScores(), 1)

        print ("Stage "+str(self.stage)+" completed")

    def nextLevel(self):
        """ 進入下一關 """
        global castle, players, bullets, bonuses, play_sounds, sounds

        del bullets[:]
        del enemies[:]
        del bonuses[:]
        # 畫玩家基地
        castle.rebuild()
        del gtimer.timers[:]

        # 加載地形圖和標識可以被子彈消滅的障礙物
        self.stage += 1
        self.level = Level(self.stage)
        self.timefreeze = False

        # 每一關四種不同類型的坦克的數量
        levels_enemies = (
            (18,2,0,0), (14,4,0,2), (14,4,0,2), (2,5,10,3), (8,5,5,2),
            (9,2,7,2), (7,4,6,3), (7,4,7,2), (6,4,7,3), (12,2,4,2),
            (5,5,4,6), (0,6,8,6), (0,8,8,4), (0,4,10,6), (0,2,10,8),
            (16,2,0,2), (8,2,8,2), (2,8,6,4), (4,4,4,8), (2,8,2,8),
            (6,2,8,4), (6,8,2,4), (0,10,4,6), (10,4,4,2), (0,8,2,10),
            (4,6,4,6), (2,8,2,8), (15,2,2,1), (0,4,10,6), (4,8,4,4),
            (3,8,3,6), (6,4,2,8), (4,4,4,8), (0,10,4,6), (0,6,4,10),
        )
        # 大於35關的關卡，一律使用第35關的敵方坦克類型
        if self.stage <= 35:
            enemies_l = levels_enemies[self.stage - 1]
        else:
            enemies_l = levels_enemies[34]

        # 打亂四種類型的敵方坦克出戰順序
        self.level.enemies_left = [0]*enemies_l[0] + [1]*enemies_l[1] + [2]*enemies_l[2] + [3]*enemies_l[3]
        random.shuffle(self.level.enemies_left)

        # 開始放遊戲聲音
        if play_sounds:
            # sounds["start"].play()
            # gtimer.add(4330, lambda :sounds["bg"].play(-1), 2)
            sounds["back"].play()

        # 初始化玩家坦克
        self.reloadPlayers()

        # 玩家坦克出現3秒後，出現敵方坦克
        gtimer.add(3000, lambda :self.spawnEnemy())

        # 遊戲結束開關
        self.game_over = False

        # 遊戲主循環開關
        self.running = True

        self.active = True

        self.draw()

        while self.running:
            time_passed = self.clock.tick(50)

            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pass
                elif event.type == pygame.QUIT:
                    quit()
                # 按下鍵盤的一個鍵觸發
                elif event.type == pygame.KEYDOWN and not self.game_over and self.active:
                    # 切換播放聲音
                    if event.key == pygame.K_m:
                        play_sounds = not play_sounds
                        if not play_sounds:
                            pygame.mixer.stop()
                        else:
                            sounds["bg"].play(-1)

                    for player in players:
                        if player.state == player.STATE_ALIVE:
                            try:
                                index = player.controls.index(event.key)
                            except:
                                pass
                            else:
                                # 按下空格鍵，表示開火
                                if index == 0:
                                    if player.fire() and play_sounds:
                                        sounds["fire"].play()
                                # 按下向上鍵，向上移動
                                elif index == 1:
                                    player.pressed[0] = True
                                # 按下向右鍵，向右移動
                                elif index == 2:
                                    player.pressed[1] = True
                                # 按下向下鍵，向下移動
                                elif index == 3:
                                    player.pressed[2] = True
                                # 按下向左鍵，向左移動
                                elif index == 4:
                                    player.pressed[3] = True
                # 鬆開按下的鍵盤鍵觸發
                elif event.type == pygame.KEYUP and not self.game_over and self.active:
                    for player in players:
                        if player.state == player.STATE_ALIVE:
                            try:
                                index = player.controls.index(event.key)
                            except:
                                pass
                            else:
                                # 鬆開向上鍵，停止向上移动
                                if index == 1:
                                    player.pressed[0] = False
                                # 鬆開向右鍵，停止向右移动
                                elif index == 2:
                                    player.pressed[1] = False
                                # 鬆開向下鍵，停止向下移动
                                elif index == 3:
                                    player.pressed[2] = False
                                # 鬆開向左鍵，停止向左移动
                                elif index == 4:
                                    player.pressed[3] = False

            # 更新玩家坦克下次出现坐標
            for player in players:
                if player.state == player.STATE_ALIVE and not self.game_over and self.active:
                    if player.pressed[0] == True:
                        player.move(self.DIR_UP);
                    elif player.pressed[1] == True:
                        player.move(self.DIR_RIGHT);
                    elif player.pressed[2] == True:
                        player.move(self.DIR_DOWN);
                    elif player.pressed[3] == True:
                        player.move(self.DIR_LEFT);
                player.update(time_passed)

            for enemy in enemies:
                if enemy.state == enemy.STATE_DEAD and not self.game_over and self.active:
                    enemies.remove(enemy)
                    if len(self.level.enemies_left) == 0 and len(enemies) == 0:
                        self.finishLevel()
                else:
                    enemy.update(time_passed)

            if not self.game_over and self.active:
                for player in players:
                    if player.state == player.STATE_ALIVE:
                        if player.bonus != None and player.side == player.SIDE_PLAYER:
                            # 觸發寶物效果
                            self.triggerBonus(bonus, player)
                            player.bonus = None
                    # 命用完就結束，否則產生新的玩家坦克
                    elif player.state == player.STATE_DEAD:
                        self.superpowers = 0
                        player.lives -= 1
                        if player.lives > 0:
                            self.respawnPlayer(player)
                            sounds["diemuc"].play()
                        else:
                            self.gameOver()

            for bullet in bullets:
                if bullet.state == bullet.STATE_REMOVED:
                    bullets.remove(bullet)
                else:
                    bullet.update()

            for bonus in bonuses:
                if bonus.active == False:
                    bonuses.remove(bonus)

            for label in labels:
                if not label.active:
                    labels.remove(label)

            # 玩家基地被擊中，遊戲結束
            if not self.game_over:
                if not castle.active:
                    self.gameOver()

            gtimer.update(time_passed)

            self.draw()


if __name__ == "__main__":
    # 計時器
    gtimer = Timer()
    # 圖像資源
    sprites = None
    # 遊戲窗口
    screen = None
    # 玩家坦克
    players = []
    # 敵方坦克
    enemies = []
    # 砲彈
    bullets = []
    # 寶物
    bonuses = []

    labels = []
    # 是否播放聲音
    play_sounds = True
    # 所有聲音
    sounds = {}

    game = Game()
    castle = Castle()
    # 開始遊戲，畫選擇界面
    game.showMenu()
