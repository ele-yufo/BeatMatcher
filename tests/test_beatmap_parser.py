"""铺面解析器测试"""

import pytest
import json
import tempfile
from pathlib import Path

from src.difficulty.beatmap_parser import BeatmapParser
from src.difficulty.models import DifficultyCategory


class TestBeatmapParser:
    """铺面解析器测试类"""
    
    def setup_method(self):
        """测试方法初始化"""
        self.parser = BeatmapParser()
    
    def create_test_beatmap_directory(self):
        """创建测试铺面目录"""
        temp_dir = Path(tempfile.mkdtemp())
        
        # 创建Info.dat
        info_data = {
            "_songName": "Test Song",
            "_beatsPerMinute": 120,
            "_difficultyBeatmapSets": [
                {
                    "_beatmapCharacteristicName": "Standard",
                    "_difficultyBeatmaps": [
                        {
                            "_difficulty": "Easy",
                            "_beatmapFilename": "Easy.dat"
                        },
                        {
                            "_difficulty": "Hard",
                            "_beatmapFilename": "Hard.dat"
                        }
                    ]
                }
            ]
        }
        
        with open(temp_dir / "Info.dat", 'w') as f:
            json.dump(info_data, f)
        
        # 创建Easy.dat (简单难度)
        easy_data = {
            "_notes": [
                {"_time": 0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
                {"_time": 1, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 1},
                {"_time": 2, "_lineIndex": 2, "_lineLayer": 0, "_type": 0, "_cutDirection": 2},
                {"_time": 4, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 3},
            ],
            "_obstacles": [
                {"_time": 1, "_lineIndex": 0, "_type": 0, "_duration": 1, "_width": 1}
            ],
            "_events": [
                {"_time": 0, "_type": 1, "_value": 1},
                {"_time": 2, "_type": 2, "_value": 2}
            ]
        }
        
        with open(temp_dir / "Easy.dat", 'w') as f:
            json.dump(easy_data, f)
        
        # 创建Hard.dat (困难难度，更多方块)
        hard_data = {
            "_notes": [
                {"_time": i * 0.25, "_lineIndex": i % 4, "_lineLayer": i % 3, "_type": i % 2, "_cutDirection": i % 8}
                for i in range(32)  # 32个方块，密度更高
            ],
            "_obstacles": [],
            "_events": []
        }
        
        with open(temp_dir / "Hard.dat", 'w') as f:
            json.dump(hard_data, f)
        
        return temp_dir
    
    def test_parse_beatmap_directory(self):
        """测试解析铺面目录"""
        beatmap_dir = self.create_test_beatmap_directory()
        
        try:
            analysis = self.parser.parse_beatmap_directory(beatmap_dir)
            
            assert analysis is not None
            assert analysis.song_name == "Test Song"
            assert len(analysis.difficulties) == 2
            
            # 检查难度统计
            easy_diff = analysis.get_difficulty_by_name("Easy")
            hard_diff = analysis.get_difficulty_by_name("Hard")
            
            assert easy_diff is not None
            assert hard_diff is not None
            
            # Easy难度应该有4个方块
            assert easy_diff.notes_count == 4
            assert easy_diff.obstacles_count == 1
            assert easy_diff.events_count == 2
            
            # Hard难度应该有32个方块
            assert hard_diff.notes_count == 32
            
            # Hard难度的NPS应该比Easy高
            assert hard_diff.nps > easy_diff.nps
            
        finally:
            # 清理临时文件
            import shutil
            shutil.rmtree(beatmap_dir)
    
    def test_difficulty_category_classification(self):
        """测试难度分类"""
        beatmap_dir = self.create_test_beatmap_directory()
        
        try:
            analysis = self.parser.parse_beatmap_directory(beatmap_dir)
            
            easy_diff = analysis.get_difficulty_by_name("Easy")
            hard_diff = analysis.get_difficulty_by_name("Hard")
            
            # Easy难度应该属于EASY分类（低NPS）
            assert easy_diff.difficulty_category == DifficultyCategory.EASY
            
            # Hard难度的NPS应该更高，可能属于MEDIUM或HARD分类
            assert hard_diff.difficulty_category in [DifficultyCategory.MEDIUM, DifficultyCategory.HARD]
            
        finally:
            import shutil
            shutil.rmtree(beatmap_dir)
    
    def test_missing_info_file(self):
        """测试缺少Info.dat文件"""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            analysis = self.parser.parse_beatmap_directory(temp_dir)
            assert analysis is None
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_invalid_json(self):
        """测试无效JSON文件"""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # 创建无效的Info.dat
            with open(temp_dir / "Info.dat", 'w') as f:
                f.write("invalid json content")
            
            analysis = self.parser.parse_beatmap_directory(temp_dir)
            assert analysis is None
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_peak_nps_calculation(self):
        """测试峰值NPS计算"""
        # 创建密集分布的方块数据
        notes_data = []
        # 在时间0-1秒内放置10个方块（高密度区间）
        for i in range(10):
            notes_data.append({
                "_time": i * 0.1,  # 0, 0.1, 0.2, ..., 0.9 拍
                "_lineIndex": 0,
                "_lineLayer": 0,
                "_type": 0,
                "_cutDirection": 0
            })
        
        # 在时间5-6秒内放置2个方块（低密度区间）
        notes_data.extend([
            {"_time": 5.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
            {"_time": 5.5, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0}
        ])
        
        diff_data = {
            "_notes": notes_data,
            "_obstacles": [],
            "_events": []
        }
        
        stats = self.parser._analyze_difficulty_data(diff_data, 120, "Test", "Standard")
        
        assert stats is not None
        # 峰值NPS应该反映最密集区间的密度
        assert stats.peak_nps > stats.nps  # 峰值应该高于平均值
    
    def test_density_variations(self):
        """测试密度变化计算"""
        # 创建变化的密度模式
        notes_data = []
        
        # 前2秒高密度：8个方块
        for i in range(8):
            notes_data.append({
                "_time": i * 0.25,  # 每0.25拍一个方块
                "_lineIndex": 0,
                "_lineLayer": 0,
                "_type": 0,
                "_cutDirection": 0
            })
        
        # 2-4秒低密度：2个方块
        notes_data.extend([
            {"_time": 4.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
            {"_time": 6.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0}
        ])
        
        diff_data = {
            "_notes": notes_data,
            "_obstacles": [],
            "_events": []
        }
        
        stats = self.parser._analyze_difficulty_data(diff_data, 120, "Test", "Standard")
        
        assert stats is not None
        assert len(stats.density_variations) > 0
        
        # 第一段应该比后面的段密度更高
        if len(stats.density_variations) >= 2:
            assert stats.density_variations[0] > stats.density_variations[-1]